# Use an official lightweight Python image.
FROM python:3.9-slim

# Set the working directory.
WORKDIR /app

# Copy the Python requirements file and install dependencies.
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the operator script.
COPY redis_operator.py /app/

# Run the operator.
CMD ["kopf", "run", "/app/redis_operator.py"]

