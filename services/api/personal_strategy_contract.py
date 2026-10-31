"""Versioned research templates; numeric limits are enforced outside the LLM."""
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator

TAIPEI = ZoneInfo('Asia/Taipei')
TYPES = ('premarket', 'intraday', 'postmarket', 'saturday')
DAILY = ('外盤情勢與重大新聞催化劑', '大盤風向與資金狀態', 'S持股逐檔檢核',
         'A/B/C觀察池快訊', '策略專屬模組', '資產與資料狀態')
WEEKLY = ('本週市場結論與Gate', 'S持股與資產估值快照', '下週條件式操作計畫',
          '研究進攻雷達', 'A/B/C全池總覽', '策略專屬研究', '觀察池同步結果與資料缺口')
TEMPLATES = {
    'stock': {'name': '股市：研究／供應鏈／執行分離', 'horizon': '數天至數月',
        'sources': [], 'entry': '研究Plane R、產業傳導Plane S與執行Plane E分開；非金融先手→確認→調節；金融僅在完整網格參數內操作。',
        'exit': '論點證偽或防線失效先停止加碼；保護池不得自動動用。',
        'tiers': 'A證據充分；B產業明確待兌現（上限8）；C早期／轉機待證。',
        'data_gate': '金融網格須錨點日期、格距、每格數量、總預算與停止條件；缺一不可給買賣網格。',
        'risks': '一般池與保護池分開，共用現金不得重複計算；供應鏈題材重疊。'},
    'value': {'name': 'Graham–Buffett 價值投資適配版', 'horizon': '數月至數年',
        'sources': ['https://www.berkshirehathaway.com/letters/1992.html'],
        'entry': '先確認正常獲利與財務品質，再於策略參考買進上限內分批；PE/PB參考區間不等於內在價值。',
        'exit': '價值修復重審減碼；獲利假設或財務品質失效重審退出；下跌不自動攤平。',
        'tiers': 'A品質與估值具支撐；B等待價格；C財務品質或資料待查。',
        'data_gate': '獲利、負債與現金流；金融看資產品質／資本。必要資料缺失不給可執行買價。',
        'risks': '價值陷阱、等待超過數月；低PE/PB不是買進充分條件。'},
    'garp': {'name': 'Peter Lynch／GARP 合理價格成長', 'horizon': '數月至數年',
        'sources': ['https://research2.fidelity.com/fidelity/screeners/commonstock/strategy.asp?simpleStrategy=%7BF61E8D5C-32C9-499B-8F6D-DD6DAF53EB78%7D'],
        'entry': '比較可比期間營收與獲利，排除一次性收益；成長已兌現且估值可接受才分批，供應鏈作佐證。',
        'exit': '成長失速、需求轉弱或估值超出設定上限時停止加碼／評估減碼。',
        'tiers': 'A成長兌現且價格合理；B待獲利確認；C題材未證。',
        'data_gate': '營收不能代替EPS；PEG需要明確期間及來源的正成長率，缺預測、虧損或非正成長不硬算。',
        'risks': '預測誤差、景氣高峰假便宜、題材集中；PEG<1不等於買進。'},
    'trend': {'name': '趨勢追蹤／時間序列動能現股適配版', 'horizon': '數週至數月',
        'sources': ['https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum'],
        'entry': '候選規則：收盤高於上升60日均線且突破前20日高點；最早下一交易時點評估進場。',
        'exit': '候選規則：跌破前20日低點或個人風險條件失效；不下跌攤平。',
        'tiers': 'A趨勢及進場確認；B待突破；C弱勢或資料不足。',
        'data_gate': '至少65個有效、連續可比較且有除權息處理的日線；未提供可重算序列不得宣稱訊號成立。',
        'risks': '盤整反覆停損、跳空與換手成本；此版不是論文12月多空期貨策略，無績效保證。'},
    'custom': {'name': '自訂策略', 'horizon': '由使用者指定', 'sources': [],
        'entry': '依自訂原文，必須有可辨識進場／加碼條件。', 'exit': '必須指定減碼／退出／失效條件。',
        'tiers': '必須指定A/B/C升降級依據。', 'data_gate': '不可執行或欠缺的條件顯示待補，不推測。',
        'risks': '自訂內容不能覆蓋風險上限、Owner隔離或禁用交易。'},
}

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Risk(Strict):
    tolerance: Literal['conservative', 'moderate', 'aggressive']
    horizon: Literal['short', 'medium', 'long']
    minimum_cash_ratio: float = Field(ge=0, le=1)
    max_position_ratio: float = Field(gt=0, le=1)
    max_sector_ratio: float = Field(gt=0, le=1)
    loss_budget_ratio: float = Field(gt=0, le=.2)
    max_drawdown_ratio: float = Field(gt=0, le=1)
    liquidity_need: str = Field(min_length=1, max_length=500)
    @model_validator(mode='after')
    def consistent(self):
        if self.max_position_ratio > self.max_sector_ratio:
            raise ValueError('單股上限不得高於產業上限')
        if self.loss_budget_ratio > self.max_drawdown_ratio:
            raise ValueError('單筆風險預算不得大於可承受損失')
        return self

class StrategyInput(Strict):
    template_id: Literal['stock', 'value', 'garp', 'trend', 'custom']
    custom_text: str = Field(default='', max_length=12000)
    risk: Risk
    private_ai_consent: bool = False
    protected_symbols: list[str] = Field(default_factory=list, max_length=50)
    @model_validator(mode='after')
    def valid(self):
        import re
        if any(not re.fullmatch(r'[A-Za-z0-9.-]{1,16}', s) for s in self.protected_symbols):
            raise ValueError('保護池代號格式錯誤')
        if self.template_id == 'custom' and len(self.custom_text.strip()) < 20:
            raise ValueError('自訂策略需包含目的、進場、退出與分級條件')
        return self

class ReportInput(Strict):
    report_type: Literal['premarket', 'intraday', 'postmarket', 'saturday']
    sync_watchlist: bool | None = None
    @model_validator(mode='after')
    def sync(self):
        if self.report_type == 'saturday' and self.sync_watchlist is None:
            raise ValueError('週六報告需明確選擇是否同步')
        if self.report_type != 'saturday' and self.sync_watchlist not in (None, False):
            raise ValueError('只有週六報告可同步')
        return self

class TierInput(Strict):
    tier: Literal['A', 'B', 'C']
    locked: bool
    expected_version: int = Field(ge=1)

class Delta(Strict):
    symbol: str = Field(pattern=r'^[A-Za-z0-9.-]{1,16}$')
    action: Literal['upsert', 'remove']
    tier: Literal['A', 'B', 'C'] = 'C'
    reason: str = Field(min_length=1, max_length=800)
    sort_order: int | None = Field(default=None, ge=0, le=49)

class Section(Strict):
    body: str = Field(min_length=1, max_length=18000)

class ReportOutput(Strict):
    sections: list[Section] = Field(min_length=6, max_length=7)
    support: list[str] = Field(min_length=1, max_length=8)
    opposition: list[str] = Field(min_length=1, max_length=8)
    invalidation: list[str] = Field(min_length=1, max_length=8)
    consistency: str = Field(min_length=1, max_length=3000)
    missing: list[str] = Field(default_factory=list, max_length=100)
    covered_symbols: list[str] = Field(max_length=500)
    delta: list[Delta] = Field(default_factory=list, max_length=10)

class SeedInput(Strict):
    documents: dict[str, str]
    @model_validator(mode='after')
    def bounded(self):
        if not 1 <= len(self.documents) <= 12 or sum(len(v) for v in self.documents.values()) > 200000:
            raise ValueError('種子最多12份、總計20萬字')
        if any(len(k) > 150 or not k.endswith('.md') for k in self.documents):
            raise ValueError('必須使用Markdown檔名')
        return self


def period(kind, now=None):
    now = now or datetime.now(TAIPEI)
    day = now.astimezone(TAIPEI).date()
    if kind == 'strategy':
        return day - timedelta(days=day.weekday())
    if kind == 'saturday' and day.weekday() != 5:
        raise ValueError('週報只限台北時間週六執行')
    return day


def preview(value: StrategyInput):
    template = TEMPLATES[value.template_id]
    warnings = []
    if value.template_id in ('value', 'garp') and value.risk.horizon == 'short':
        warnings.append('此學派通常需數月以上；短期資金需求不適合，請修改期限或策略。')
    if value.risk.minimum_cash_ratio + value.risk.max_position_ratio > 1:
        warnings.append('單股實際上限會受最低現金比例限制。')
    if value.template_id == 'custom':
        for term in ('進場', '退出', 'A', 'B', 'C'):
            if term not in value.custom_text:
                warnings.append(f'自訂策略待補：{term}')
    rules = {**value.model_dump(), 'template': template, 'template_version': '2026-10-31.1',
             'cash_only': True, 'max_sync_changes': 10, 'max_watchlist': 50,
             'b_capacity': 8 if value.template_id == 'stock' else 50}
    rules['risk']['max_position_ratio'] = min(value.risk.max_position_ratio, 1-value.risk.minimum_cash_ratio)
    return {'rules': rules, 'warnings': warnings, 'blocked': any('請修改' in w or '待補' in w for w in warnings),
            'markdown': f"# {template['name']}\n\n## 操作邏輯\n{template['entry']}\n\n## 退出與失效\n{template['exit']}\n\n## 分級\n{template['tiers']}\n\n## 資料門檻\n{template['data_gate']}\n\n## 限制\n{template['risks']}\n\n## 個人補充\n{value.custom_text or '無'}"}
