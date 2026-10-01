FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY main.py cohort_build.py independent_cohort_run.py outcome_run.py sensitivity_run.py eventize_run.py eventize_run_v2.py matched_feature_run.py matched_feature_run_v2.py validation_run.py prospective_registry_run.py /app/
RUN python -c "import cohort_build; cohort_build.self_test(); print('COHORT_SELF_TEST PASS')"
RUN python -c "import independent_cohort_run; independent_cohort_run.self_test(); print('INDEPENDENT_COHORT_SELF_TEST PASS')"
RUN python -c "import outcome_run; outcome_run.self_test(); print('OUTCOME_SELF_TEST PASS')"
RUN python -c "import sensitivity_run; sensitivity_run.self_test(); print('SENSITIVITY_SELF_TEST PASS')"
RUN python -c "import eventize_run_v2; eventize_run_v2.self_test(); print('EVENTIZE_V2_SELF_TEST PASS')"
RUN python -c "import matched_feature_run; matched_feature_run.self_test(); print('MATCHED_FEATURE_V1_SELF_TEST PASS')"
RUN python -c "import numpy as np, matched_feature_run_v2 as m; sid=np.asarray([0,1,2,3],dtype=np.int32); liq=np.asarray([100.0,105.0,300.0,95.0]); assert m._nearest_three(0,100.0,sid,liq,set()).tolist()==[1,3,2]; assert len(m._nearest_three(0,100.0,sid,liq,{3}))==0; print('MATCHED_FEATURE_V2_SELF_TEST PASS')"
RUN python -c "import validation_run; validation_run.self_test(); print('VALIDATION_SELF_TEST PASS')"
RUN python -c "import prospective_registry_run; prospective_registry_run.self_test(); print('PROSPECTIVE_REGISTRY_SELF_TEST PASS')"
RUN useradd --create-home --uid 10001 research
USER 10001
ENTRYPOINT ["python", "/app/main.py"]
