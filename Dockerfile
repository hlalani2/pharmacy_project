# Use the official Heroku Python image as a base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application files
COPY . .

# Run the application
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]

