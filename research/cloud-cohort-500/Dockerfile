FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt
COPY main.py cohort_build.py /app/
RUN python -c "import cohort_build; cohort_build.self_test(); print('COHORT_SELF_TEST PASS')"
RUN useradd --create-home --uid 10001 research
USER 10001
ENTRYPOINT ["python", "/app/main.py"]
