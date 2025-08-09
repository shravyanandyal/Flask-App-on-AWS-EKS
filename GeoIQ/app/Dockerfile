# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Inform Docker that the container listens on port 8080
EXPOSE 8080

# Run the application using Gunicorn when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]