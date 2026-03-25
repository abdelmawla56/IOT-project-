FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code and configuration
COPY . .

# Create data directory for SQLite
RUN mkdir -p data

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the world engine
CMD ["python", "main.py"]
