from pathlib import Path


ROOT=Path(__file__).parents[1]


def test_private_pipeline_scheduler_contract_is_fixed_owner_scoped_and_dev_gated():
    script=(ROOT/"scripts/gcp/apply-private-pipeline-schedulers-dev.sh").read_text(encoding="utf-8")
    assert script.count("janus-private-pipeline-")==4
    for name,cron in (
        ("0740","40 7 * * MON-FRI"),
        ("1100","0 11 * * MON-FRI"),
        ("1400","0 14 * * MON-FRI"),
        ("2130","30 21 * * MON-FRI"),
    ):
        assert f"janus-private-pipeline-{name}|{cron}" in script
    assert "--time-zone=Asia/Taipei" in script
    assert "/jobs/${job}:run" in script and 'job="janus-private-pipeline"' in script
    assert "--message-body='{}'" in script
    assert "janus-ingestion-scheduler@${project}.iam.gserviceaccount.com" in script
    assert "--role=roles/run.invoker" in script
    assert "ALLOW_DEV_SCHEDULER_APPLY" in script and 'JANUS_ENVIRONMENT:-}" != "dev"' in script


def test_private_pipeline_deploy_removes_fixed_valuation_default():
    script=(ROOT/"scripts/gcp/deploy-dev.sh").read_text(encoding="utf-8")
    private=script.split("private-pipeline)",2)[2].split(";;",1)[0]
    assert '--remove-env-vars="VALUATION_DATE"' in private
    assert '--remove-secrets="CORE_CATALOG_PASSWORD,PRIVATE_DATABASE_URL,PRIVATE_CATALOG_PASSWORD,JANUS_PIPELINE_POSTGRES_BUNDLE"' in private
    assert 'CORE_CATALOG_PASSWORD=janus-postgres-api-bundle:latest' not in private
