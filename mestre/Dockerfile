FROM python:3.11-slim
WORKDIR /app
COPY mestre/mestre.py .
RUN pip install flask psycopg2-binary
EXPOSE 5000
CMD ["python", "mestre.py"]