# Use a Playwright-maintained image that has Chromium and Python pre-installed
FROM mcr.microsoft.com/playwright/python:latest 

# Set the working directory
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (including library_streamlit_app.py)
COPY . .

# Set the command to run the Streamlit application
# We use the PORT environment variable provided by DigitalOcean
CMD ["streamlit", "run", "library_streamlit_app.py", "--server.port", "8080", "--server.enableCORS", "false"]