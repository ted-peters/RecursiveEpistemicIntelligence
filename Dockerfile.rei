# Local-first REI API and browser UI; model weights are served by Ollama.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .
USER 65532:65532
EXPOSE 7861
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7861/health',timeout=2)" || exit 1
CMD ["python","-m","rei0.local_ai_cli","serve","--host","0.0.0.0","--allow-remote-bind"]
