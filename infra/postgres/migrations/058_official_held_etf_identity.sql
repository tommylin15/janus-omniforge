\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- 官方來源：證券櫃檯買賣中心 00719B 債券 ETF 商品規格
-- https://wwwov.tpex.org.tw/web/etf/etf_specification_bond_detail.php?code=00719B&l=zh-tw
-- 官方證櫃債字第10700020421號：2018-02-01 上櫃、簡稱「元大美債1-3」。
-- 僅新增已核實的 ETF instrument；不併入 TWSE/TPEx 上市櫃「股票」1988 檔母體。
-- 不寫個人交易、股數、價格、PnL，不變動既有身份或已存在的相異 stock_master 記錄。
CREATE TABLE IF NOT EXISTS control.official_instrument_identity_provenance (
    symbol text PRIMARY KEY REFERENCES control.stock_master(symbol),
    source_id text NOT NULL,
    source_url text NOT NULL,
    listed_on date NOT NULL,
    verified_on date NOT NULL,
    instrument_kind text NOT NULL
);

INSERT INTO control.stock_master (symbol, name, market, enabled)
VALUES ('00719B', '元大美債1-3', 'TPEX', true)
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO control.official_instrument_identity_provenance
    (symbol, source_id, source_url, listed_on, verified_on, instrument_kind)
VALUES
    ('00719B', 'tpex_official_bond_etf',
     'https://wwwov.tpex.org.tw/web/etf/etf_specification_bond_detail.php?code=00719B&l=zh-tw',
     DATE '2018-02-01', DATE '2026-10-15', 'BOND_ETF')
ON CONFLICT (symbol) DO NOTHING;

-- PHASE: acceptance
SELECT
    EXISTS (
        SELECT 1 FROM control.stock_master sm
        JOIN control.official_instrument_identity_provenance p USING (symbol)
        WHERE sm.symbol='00719B' AND sm.name='元大美債1-3'
          AND sm.market='TPEX' AND sm.enabled IS TRUE
          AND p.source_id='tpex_official_bond_etf'
          AND p.listed_on=DATE '2018-02-01'
          AND p.verified_on=DATE '2026-10-15'
          AND p.instrument_kind='BOND_ETF'
          AND p.source_url='https://wwwov.tpex.org.tw/web/etf/etf_specification_bond_detail.php?code=00719B&l=zh-tw'
    ),
    NOT has_table_privilege('janus_public_api',
        'control.official_instrument_identity_provenance', 'INSERT'),
    NOT EXISTS (
        SELECT 1 FROM control.market_universe_members WHERE symbol='00719B'
    );

INSERT INTO control.schema_migrations(version) VALUES
    ('058_official_held_etf_identity') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
