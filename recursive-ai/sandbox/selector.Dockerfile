FROM python:3.12-alpine
WORKDIR /opt/selector
COPY research/mixed_inference.py research/public_queries.py research/query_fallback.py research/oracle_process.py /opt/selector/research/
USER 65534:65534
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
ENTRYPOINT ["python", "-m", "research.oracle_process"]
