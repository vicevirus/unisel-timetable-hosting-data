import requests
import runpy
import tempfile
import os

# URL of the script to download
url = "https://raw.githubusercontent.com/vicevirus/unisel-timetable-hosting-data/main/scrapeRepo.py"

# Sending a GET request to the URL
response = requests.get(url)

# Checking if the request was successful
if response.status_code == 200:
    # Use tempfile to create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as tmp_file:
        tmp_file_name = tmp_file.name
        # Writing the content of the response to the temporary file
        tmp_file.write(response.content)
    
    # Now run the downloaded script
    runpy.run_path(tmp_file_name)

    # Clean up the temporary file
    os.unlink(tmp_file_name)

    print("Script executed successfully.")
else:
    print("Failed to download the script.")
