FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install -U pdm

ENV PDM_CHECK_UPDATE=false

COPY pyproject.toml pdm.lock README.md ./

# Install Python dependencies
RUN pdm install --check --prod --no-editable

RUN pip install aider-chat

COPY . .

EXPOSE 8000

CMD ["pdm", "run", "start"] 