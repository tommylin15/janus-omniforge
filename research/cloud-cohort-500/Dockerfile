FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY main.py cohort_build.py outcome_run.py sensitivity_run.py eventize_run.py matched_feature_run.py /app/
RUN python -c "import cohort_build; cohort_build.self_test(); print('COHORT_SELF_TEST PASS')"
RUN python -c "import outcome_run; outcome_run.self_test(); print('OUTCOME_SELF_TEST PASS')"
RUN python -c "import sensitivity_run; sensitivity_run.self_test(); print('SENSITIVITY_SELF_TEST PASS')"
RUN python -c "import eventize_run; eventize_run.self_test(); print('EVENTIZE_SELF_TEST PASS')"
RUN python -c "import matched_feature_run; matched_feature_run.self_test(); print('MATCHED_FEATURE_SELF_TEST PASS')"
RUN useradd --create-home --uid 10001 research
USER 10001
ENTRYPOINT ["python", "/app/main.py"]
