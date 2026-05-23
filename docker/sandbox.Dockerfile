FROM python:3.11-slim

# Install common data-science packages so the agent can do real analysis
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    pandas==2.2.2 \
    matplotlib==3.9.0 \
    scipy==1.13.1 \
    scikit-learn==1.5.0 \
    requests==2.32.3

# Create a non-root user for extra isolation
RUN useradd -m -u 1001 sandbox
USER sandbox

WORKDIR /sandbox
