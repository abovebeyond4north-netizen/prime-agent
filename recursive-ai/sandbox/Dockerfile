FROM python:3.12-alpine@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4
WORKDIR /opt/lab
COPY runner_harness.py /opt/lab/runner_harness.py
USER 65534:65534
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
ENTRYPOINT ["python", "-I", "/opt/lab/runner_harness.py"]
