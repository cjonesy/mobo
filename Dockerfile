FROM python:3.8-slim

WORKDIR /usr/src/mobo

COPY . .
RUN pip install --upgrade pip \
&&  pip install --no-cache-dir .

CMD ["python", "-m", "mobo"]
