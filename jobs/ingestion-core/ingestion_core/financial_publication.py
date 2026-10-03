"""Official filing-index evidence; upload times never identify numeric revisions alone."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re


class FilingIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cells, self.cell, self.link = [], [], None, ""
        self.headers, self.inputs = [], {}

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells, self.link = [], ""
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "input":
            attributes = dict(attrs)
            if attributes.get("name"):
                self.inputs[attributes["name"]] = attributes.get("value", "")
            if "document.fm.CID.value" in attributes.get("onclick", ""):
                self.link = attributes["onclick"]
        elif tag == "a":
            href = dict(attrs).get("href", "")
            if "readfile2(" in href:
                self.link = href

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            value = "".join(self.cell).strip()
            if tag == "th":
                self.headers.append(value)
            else:
                self.cells.append(value)
            self.cell = None
        elif tag == "tr" and self.link:
            self.rows.append((list(self.cells), self.link))


def parse_filing_index(html, symbol, fiscal_year, *, report_scope="consolidated"):
    scopes = {"consolidated": ("IFRSs合併財報", "AI1"),
              "separate": ("IFRSs個別財報", "AI2"), "individual": ("IFRSs個體財報", "AI3")}
    if report_scope not in scopes:
        raise ValueError("unsupported official report scope")
    description, file_kind = scopes[report_scope]
    parser = FilingIndex()
    parser.feed(html)
    if not {"上傳日期", "電子檔案"}.issubset(parser.headers):
        raise ValueError("official filing index headers missing")
    result = []
    for cells, link in parser.rows:
        if len(cells) != 11 or cells[0] != symbol or cells[2] != "財務報告書":
            continue
        if cells[5] != description:
            continue
        filename = re.fullmatch(r'javascript:readfile2\("A","([0-9]{4})","([0-9]{6}_[0-9]{4}_AI[0-9]+\.pdf)"\);', link)
        period = re.fullmatch(r"([0-9]+) 年 第([一二三四])季", cells[1])
        uploaded = re.fullmatch(r"([0-9]{3})/([0-9]{2})/([0-9]{2}) ([0-9]{2}:[0-9]{2}:[0-9]{2})", cells[9])
        if not filename or filename[1] != symbol or not period or not uploaded:
            raise ValueError("official filing index schema changed")
        year, quarter = int(period[1]) + 1911, "一二三四".index(period[2]) + 1
        if year != fiscal_year or filename[2] != f"{year}{quarter:02d}_{symbol}_{file_kind}.pdf":
            raise ValueError("filing filename does not match fiscal identity")
        instant = datetime.fromisoformat(f"{int(uploaded[1])+1911}-{uploaded[2]}-{uploaded[3]}T{uploaded[4]}")
        result.append({"symbol": symbol, "fiscal_year": year, "fiscal_quarter": quarter, "report_scope": report_scope,
                       "filename": filename[2], "official_uploaded_at": instant.replace(tzinfo=timezone(timedelta(hours=8))).isoformat(),
                       "amendment_status": cells[10], "numeric_revision_verified": False})
    return result


def parse_correction_index(html, fiscal_year, fiscal_quarter):
    parser = FilingIndex()
    parser.feed(html)
    if not {"公司代號", "公告日期", "詳細資料"}.issubset(parser.headers):
        raise ValueError("official correction index headers missing")
    if parser.inputs.get("YEAR_SEASON") != f"{fiscal_year}{fiscal_quarter:02d}":
        raise ValueError("correction query fiscal identity mismatch")
    result = []
    for cells, action in parser.rows:
        if len(cells) != 6 or cells[3] != "IFRSs合併財報":
            continue
        detail = dict(re.findall(r'document\.fm\.(SKEY|CID|RID|DTYPE)\.value="([A-Za-z0-9]+)"', action))
        if detail.get("CID") != cells[0] or set(detail) != {"SKEY", "CID", "RID", "DTYPE"}:
            raise ValueError("correction detail identity mismatch")
        announcement = datetime.strptime(cells[2], "%Y%m%d").date().isoformat()
        result.append({"symbol": cells[0], "fiscal_year": fiscal_year,
                       "fiscal_quarter": fiscal_quarter, "official_announcement_date": announcement,
                       "time_precision": "date", "correction_description": cells[4],
                       "detail_parameters": detail, "numeric_revision_verified": False})
    return result


class XbrlReport(HTMLParser):
    """Read inline facts with their actual entity, dates, dimensions and units."""
    def __init__(self):
        super().__init__()
        self.contexts, self.units, self.facts, self.metadata = {}, {}, [], {}
        self.context, self.unit, self.fact, self.field = None, None, None, None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "xbrli:context":
            self.context = {"id": attributes["id"], "dimensioned": False}
        elif tag in {"xbrldi:explicitmember", "xbrldi:typedmember", "xbrli:scenario", "xbrli:segment"} and self.context is not None:
            self.context["dimensioned"] = True
        elif tag == "xbrli:unit":
            self.unit = {"id": attributes["id"], "measures": []}
        elif tag in {"xbrli:identifier", "xbrli:startdate", "xbrli:enddate", "xbrli:instant", "xbrli:measure"}:
            self.field, self.buffer = tag, []
        elif tag == "ix:nonfraction" or (tag == "ix:nonnumeric" and attributes.get("name") in {
                "tifrs-notes:CompanyID", "tifrs-notes:Year", "tifrs-notes:Quarter",
                "tifrs-notes:ReportCategory", "tifrs-notes:IndustrySector", "tifrs-notes:ReportType"}):
            if self.fact is not None:
                raise ValueError("nested inline numeric fact")
            self.fact = attributes | {"text": [], "tag": tag}

    def handle_data(self, data):
        if self.field:
            self.buffer.append(data)
        if self.fact is not None:
            self.fact["text"].append(data)

    def handle_endtag(self, tag):
        if tag == self.field:
            value = "".join(self.buffer).strip()
            if self.context is not None:
                self.context[tag.split(":")[1]] = value
            if self.unit is not None and tag == "xbrli:measure":
                self.unit["measures"].append(value)
            self.field = None
        elif tag == "xbrli:context" and self.context is not None:
            identity = self.context["id"]
            if identity in self.contexts:
                raise ValueError("duplicate XBRL context identity")
            self.contexts[identity], self.context = self.context, None
        elif tag == "xbrli:unit" and self.unit is not None:
            self.units[self.unit["id"]], self.unit = self.unit["measures"], None
        elif self.fact is not None and tag == self.fact["tag"]:
            if tag == "ix:nonfraction":
                self.facts.append(self.fact)
            else:
                name, value = self.fact["name"], "".join(self.fact["text"]).strip()
                if name in self.metadata and self.metadata[name] != value:
                    raise ValueError("conflicting XBRL report metadata")
                self.metadata[name] = value
            self.fact = None


def parse_xbrl_report(html, symbol, fiscal_year, fiscal_quarter, *, report_scope="consolidated", include_comparatives=False):
    """Read current facts and optional same-filing comparatives without inventing publication."""
    end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}.get(fiscal_quarter)
    if end is None:
        raise ValueError("invalid financial quarter")
    end = f"{fiscal_year}-{end}"
    parser = XbrlReport()
    parser.feed(html)
    if not parser.contexts or not parser.units or not parser.facts:
        raise ValueError("official inline XBRL report missing")
    if {context.get("identifier") for context in parser.contexts.values()} != {symbol}:
        raise ValueError("XBRL report company identity mismatch")
    for name, expected in (("CompanyID", symbol), ("Year", str(fiscal_year)), ("Quarter", str(fiscal_quarter))):
        if parser.metadata.get("tifrs-notes:" + name) != expected:
            raise ValueError("XBRL primary report identity mismatch")
    scopes = {"consolidated": "Consolidated report", "separate": "Individual report", "individual": "Individual report"}
    if report_scope not in scopes or parser.metadata.get("tifrs-notes:ReportCategory") != scopes[report_scope]:
        raise ValueError("XBRL report scope mismatch")
    rows = {}
    for fact in parser.facts:
        if fact.get("name", "").split(":")[0] not in {"ifrs-full", "tifrs-SCF", "tifrs-bsci-ci", "tifrs-bsci-basi", "tifrs-bsci-ins", "tifrs-bsci-fh", "tifrs-bsci-bd", "tifrs-bsci-mim"}:
            continue  # Generic note Amount1/Amount2 concepts do not identify statement metrics.
        if fact.get("xsi:nil") == "true":
            continue
        context = parser.contexts.get(fact.get("contextref"))
        if context is None:
            raise ValueError("inline fact references missing context")
        last = context.get("instant", context.get("enddate"))
        first = context.get("startdate", last)
        comparative_end = f"{fiscal_year-1}-{end[5:]}"
        if context["dimensioned"] or last not in ({end, comparative_end} if include_comparatives else {end}) or not first or first[:4] != last[:4]:
            continue
        measures = parser.units.get(fact.get("unitref"))
        if measures == ["iso4217:TWD"]:
            unit = "TWD"
        elif measures == ["iso4217:TWD", "xbrli:shares"]:
            unit = "TWD_per_share"
        else:
            continue
        if fact.get("format", "").split(":")[-1] != "numdotdecimal" or fact.get("sign", "") not in {"", "-"}:
            raise ValueError("unsupported inline numeric transformation")
        try:
            value = Decimal("".join(fact["text"]).strip().replace(",", ""))
            scale = int(fact.get("scale", "0"))
            if not value.is_finite() or scale not in {0, 3}:
                raise ValueError("unsupported inline numeric scale")
            value *= Decimal(10) ** scale
            if fact.get("sign") == "-":
                value = -value
        except (InvalidOperation, ValueError) as error:
            raise ValueError("invalid inline numeric fact") from error
        quarter_start = f"{last[:4]}-{(fiscal_quarter-1)*3+1:02d}-01"
        basis = "snapshot" if first == last else "year_to_date" if first == f"{last[:4]}-01-01" else "single_quarter" if first == quarter_start else None
        if basis is None:
            continue
        key = (fact["name"], first, last, unit)
        if key in rows and rows[key]["value"] != str(value):
            raise ValueError("conflicting inline facts")
        rows[key] = {"symbol": symbol, "fiscal_year": fiscal_year, "fiscal_quarter": fiscal_quarter,
                     "concept": fact["name"], "context_id": fact["contextref"], "period_start": first,
                     "period_end": last, "period_basis": basis, "unit": unit, "value": str(value),
                     "is_single_quarter": first == quarter_start and first != last,
                     "report_scope": report_scope, "industry_sector": parser.metadata.get("tifrs-notes:IndustrySector"),
                     "report_type": parser.metadata.get("tifrs-notes:ReportType"),
                     "numeric_revision_verified": False}
    if not rows:
        raise ValueError("XBRL report has no matching fiscal period facts")
    return list(rows.values())


def normalise_xbrl_financials(html, symbol, fiscal_year, fiscal_quarter, *, received_at, report_scope="consolidated"):
    """Current research observations; receipt does not prove original publication."""
    received = datetime.fromisoformat(str(received_at).replace("Z", "+00:00"))
    if received.tzinfo is None:
        raise ValueError("financial receipt time must include timezone")
    concepts = {
        "Revenue": ("income", "revenue"), "ProfitLoss": ("income", "net_income"),
        "ProfitLossAttributableToOwnersOfParent": ("income", "net_income_parent"),
        "BasicEarningsLossPerShare": ("income", "eps"),
        "Assets": ("balance", "total_assets"), "Liabilities": ("balance", "total_liabilities"),
        "Equity": ("balance", "total_equity"),
        "EquityAttributableToOwnersOfParent": ("balance", "equity_parent"),
        "CashFlowsFromUsedInOperatingActivities": ("cash_flow", "operating_cash_flow"),
        "CashFlowsFromUsedInInvestingActivities": ("cash_flow", "investing_cash_flow"),
        "CashFlowsFromUsedInFinancingActivities": ("cash_flow", "financing_cash_flow"),
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities": ("cash_flow", "ppe_capex"),
    }
    result = []
    facts = parse_xbrl_report(html, symbol, fiscal_year, fiscal_quarter, report_scope=report_scope, include_comparatives=True)
    for fact in facts:
        if fact["period_end"][:4] != str(fiscal_year):
            continue
        if not fact["concept"].startswith("ifrs-full:") or fact["concept"].split(":")[1] not in concepts:
            continue
        statement, metric = concepts[fact["concept"].split(":")[1]]
        if (statement == "balance") != (fact["period_basis"] == "snapshot"):
            raise ValueError("financial statement context mismatch")
        if (metric == "eps") != (fact["unit"] == "TWD_per_share"):
            raise ValueError("financial statement metric unit mismatch")
        result.append({**fact, "statement_type": statement,
                       "metric": metric + "_" + fact["period_basis"], "currency": "TWD",
                       "fiscal_period_end": fact["period_end"], "published_at": None,
                       "publication_time_authoritative": False,
                       "availability_at": received.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                       "observed_at": received.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                       "availability_basis": "source_response_receipt",
                       "share_basis_status": "unknown" if metric == "eps" else "not_applicable",
                       "historical_publication_status": "unknown"})
    if not result:
        raise ValueError("financial report has no supported research metrics")
    for row in result:
        row["financial_feature_version"] = "same-filing-comparatives-v1"
    for concept, metric in (("BasicEarningsLossPerShare", "eps"), ("ProfitLossAttributableToOwnersOfParent", "net_income_parent")):
        candidates = [fact for fact in facts if fact["concept"] == "ifrs-full:" + concept]
        for basis in ("single_quarter", "year_to_date"):
            current = [fact for fact in candidates if fact["period_basis"] == basis and fact["period_end"][:4] == str(fiscal_year)]
            previous = [fact for fact in candidates if fact["period_basis"] == basis and fact["period_end"][:4] == str(fiscal_year-1)]
            if len(current) != 1 or len(previous) != 1 or current[0]["unit"] != previous[0]["unit"]:
                continue
            prior_value = Decimal(previous[0]["value"])
            if not prior_value:
                continue
            template = next(row for row in result if row["concept"] == current[0]["concept"] and row["period_basis"] == basis)
            result.append({**template, "metric": metric + "_yoy_percent_same_filing", "unit": "percent",
                "value": str((Decimal(current[0]["value"])-prior_value)/abs(prior_value)*100),
                "comparison_value": previous[0]["value"], "comparison_period_end": previous[0]["period_end"],
                "context_id": current[0]["context_id"] + "|" + previous[0]["context_id"],
                "share_basis_status": "same_filing_reported_comparison" if metric == "eps" else "not_applicable"})
            break
    return result
