# FINOPS-AB：Iceberg 只留目前 snapshot

2026-10-18 使用者決定取消「因有效 snapshot／研究／報告引用而保留檔案」的限制，未來研究／模型／snapshot 另訂；進一步明確選擇 **只保留目前 snapshot；其餘可清理**。

本次 Core／Mart 維護移除非 current snapshot 的 named tag／branch，過期其餘所有 snapshot；不保留24小時，不以 execution／研究／模型／報告／publication 引用阻擋清理，也不要求完整 external reference fence。current snapshot 內容與必要資料檔仍須完整讀回，Private Owner 交易不在範圍。

實體清理保留現有7日檔齡、generation 條件、dev bucket/table allowlist、writer／mutation lock與catalog pointer防競爭。metadata JSON 沿既有目前 pointer／metadata log及10代上限，不在本次擴張重訂。Core execution manifest沿既有90日期限與active execution操作保護；它不再替歷史 Iceberg snapshot取得永久保留。

這項人工決策允許歷史研究／報告／snapshot無法重播，不能寫成仍具完整PIT歷史回放。未來研究／模型如何重建及保留另議，本次不建立新政策框架。發布／compaction／過期／實刪及資料讀回仍各自保存真實證據，文件或tests成功不代表live已生效。
