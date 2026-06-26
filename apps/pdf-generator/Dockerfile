FROM public.ecr.aws/lambda/microvms:al2023-minimal
RUN dnf install -y python3 python3-pip weasyprint-fonts && dnf clean all
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
WORKDIR /app
COPY main.py /app/main.py
COPY templates /app/templates
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
