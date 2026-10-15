\set ON_ERROR_STOP on
BEGIN;
SET ROLE janus_control;

-- 官方來源：證券櫃檯買賣中心 00697B 債券 ETF 商品規格
-- https://www.tpex.org.tw/storage/eb_data/10606/10600159891.htm
-- 官方證櫃債字第10600159891號：2017-06-23 上櫃、簡稱「元大美債7-10」。
-- 僅新增已核實的 ETF instrument；不併入 TWSE/TPEx 上市櫃「股票」1988 檔母體。
-- 不寫個人交易、股數、價格、PnL，不變動既有身份或已存在的相異 stock_master 記錄。
INSERT INTO control.stock_master (symbol, name, market, enabled)
VALUES ('00697B', '元大美債7-10', 'TPEX', true)
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO control.official_instrument_identity_provenance
    (symbol, source_id, source_url, listed_on, verified_on, instrument_kind)
VALUES
    ('00697B', 'tpex_official_bond_etf',
     'https://www.tpex.org.tw/storage/eb_data/10606/10600159891.htm',
     DATE '2017-06-23', DATE '2026-10-15', 'BOND_ETF')
ON CONFLICT (symbol) DO NOTHING;

-- PHASE: acceptance
SELECT
    EXISTS (
        SELECT 1 FROM control.stock_master sm
        JOIN control.official_instrument_identity_provenance p USING (symbol)
        WHERE sm.symbol='00697B' AND sm.name='元大美債7-10'
          AND sm.market='TPEX' AND sm.enabled IS TRUE
          AND p.source_id='tpex_official_bond_etf'
          AND p.listed_on=DATE '2017-06-23'
          AND p.verified_on=DATE '2026-10-15'
          AND p.instrument_kind='BOND_ETF'
          AND p.source_url='https://www.tpex.org.tw/storage/eb_data/10606/10600159891.htm'
    ),
    NOT has_table_privilege('janus_public_api',
        'control.official_instrument_identity_provenance', 'INSERT'),
    NOT EXISTS (
        SELECT 1 FROM control.market_universe_members WHERE symbol='00697B'
    );

INSERT INTO control.schema_migrations(version) VALUES
    ('060_official_held_bond_etf_identity') ON CONFLICT DO NOTHING;
RESET ROLE;
COMMIT;
