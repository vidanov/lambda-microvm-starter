FROM public.ecr.aws/lambda/microvms:al2023-minimal

# System tools + Python
RUN dnf install -y python3 python3-pip git jq tmux unzip && dnf clean all

# Python environment with marimo + boto3
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Node.js (needed for Kiro CLI)
RUN curl -fsSL https://rpm.nodesource.com/setup_24.x | bash - \
    && dnf install -y nodejs && dnf clean all

# Install Kiro CLI
RUN curl --proto '=https' --tlsv1.2 -sSf \
    'https://desktop-release.q.us-east-1.amazonaws.com/latest/kirocli-aarch64-linux.zip' \
    -o /tmp/kirocli.zip \
    && unzip /tmp/kirocli.zip -d /tmp \
    && bash /tmp/kirocli/install.sh --force --no-confirm \
    && rm -rf /tmp/kirocli /tmp/kirocli.zip

# Install AWS CLI v2 (ARM64)
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o /tmp/awscliv2.zip \
    && unzip /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

WORKDIR /app/notebooks
COPY start.sh /app/start.sh
COPY app.py /app/notebooks/app.py
RUN chmod +x /app/start.sh

EXPOSE 2718
CMD ["/app/start.sh"]
