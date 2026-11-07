FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m app && chown -R app /app
USER app
ENV SHOW_RECENT=0
EXPOSE 7860
CMD ["gunicorn","-b","0.0.0.0:7860","--workers","1","--threads","4","--timeout","120","app:app"]
