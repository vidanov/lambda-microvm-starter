FROM public.ecr.aws/lambda/microvms:al2023-minimal
RUN dnf install -y python3 python3-pip && dnf clean all
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --upgrade pip
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
WORKDIR /app
COPY app.py /app/app.py
EXPOSE 2718
CMD ["marimo", "edit", "/app/app.py", "--host", "0.0.0.0", "--port", "2718", "--headless", "--no-token"]
