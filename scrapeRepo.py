import asyncio
import subprocess
import orjson as json
import os
import requests
import re
import httpx
from bs4 import BeautifulSoup
from github import Github

from http import HTTPStatus
from github import GithubException

httpx_client = httpx.AsyncClient()

github_token = os.getenv('TOKEN_GITHUB')

if github_token:
    gh = Github(github_token)
else:
    gh = Github()



GITHUB_USERNAME = 'vicevirus'
GITHUB_REPO_NAME = 'unisel-timetable-hosting-data'
repo = gh.get_user(GITHUB_USERNAME).get_repo(GITHUB_REPO_NAME)

async def get_latest_semester_codes(github_repo, file_path):
    # Scrape the website to get the latest semester codes
    url = "http://etimetable.unisel.edu.my"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all anchor tags with the semester code
    sa_codes = []
    bj_codes = []
    f_codes = []

    sa_table = soup.find_all('table')[0]
    bj_table = soup.find_all('table')[1]
    f_table = soup.find_all('table')[2]

    sa_links = sa_table.find_all('a')
    bj_links = bj_table.find_all('a')
    f_links = f_table.find_all('a')

    for link in sa_links:
        sa_codes.append(link.text.split()[-1])

    for link in bj_links:
        bj_codes.append(link.text.split()[-1])

    for link in f_links:
        f_codes.append(link.text.split()[-1])

    sa_codes[0] = sa_codes[0].replace('(', '').replace(')', '')
    bj_codes[0] = bj_codes[0].replace('(', '').replace(')', '')
    f_codes[0] = f_codes[0].replace('(', '').replace(')', '')

    latest_semester_codes = {
        "SA": sa_codes,
        "BJ": bj_codes,
        "F": f_codes
    }

    # Convert the dictionary to JSON format
    file_contents = json.dumps(latest_semester_codes)
    try:
        file = github_repo.get_contents(file_path)
        existing_data = json.loads(file.decoded_content)

        # Compare the existing data with the new data
        if existing_data == latest_semester_codes:
            print("No updates required for the latest semester codes.")
            return latest_semester_codes
    except GithubException as e:
        if e.status != 404:
            raise e

    try:
        # Try to get the file from GitHub
        file = github_repo.get_contents(file_path)

        # Update the file with the latest data
        github_repo.update_file(
            file_path,
            f"Update {file_path}",
            file_contents,
            sha=file.sha
        )
    except:
        # If the file does not exist, create a new file with the latest data
        github_repo.create_file(
            file_path,
            f"Create {file_path}",
            file_contents
        )

    return latest_semester_codes



def fetch_data(campus, semester):
    if (campus == "F"):
        campus = "BJ"
        
    subjectPage = requests.get(f"http://etimetable.unisel.edu.my/{campus}{semester}/{campus}{semester}_subjects_days_vertical.html")
    teachersPage = requests.get(f"http://etimetable.unisel.edu.my/{campus}{semester}/{campus}{semester}_teachers_days_vertical.html")

    subjectSoup = BeautifulSoup(subjectPage.content, 'html.parser')
    teachersSoup = BeautifulSoup(teachersPage.content, 'html.parser')

    subjects = subjectSoup.find_all('li')
    lecturers = teachersSoup.find_all('li')
    availSub = subjectSoup.select("table > tbody > tr")
    
    def process_names(items):
        names = []
        for item in items:
            item = item.text.strip('\n').strip()
            if 'Subject' in item:
                item = item.replace('Subject', '').strip()
            names.append({"subject": item})
        return names

    lecturers_data = process_names(lecturers)
    subjects_data = process_names(subjects)
    
    def get_day_from_index(index, campus):    
        if (campus == "SA"):
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            return days[index % 7]
        elif (campus == "BJ"):
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            return days[index % 5]
        elif (campus == "F"):
            days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
            return days[index % 5]
    num_rows = 8 if campus == "SA" else 6
    subjects_time_data = []
    subject_idx = 0
    for subject in subjects_data:
        subject_name = subject["subject"]
        subject_timetable_data = {}
        idx = 0
        for time in availSub[subject_idx*num_rows:subject_idx*num_rows+num_rows]:
            time = time.text.strip('\n').strip()
            time = re.split('\n', time)

            if any("Timetable generated with FET" in t for t in time):
                continue

            time.pop(0)

            day = get_day_from_index(idx, campus)

            if subject_name not in subject_timetable_data:
                subject_timetable_data['subjectName'] = subject_name

            subject_timetable_data[day] = time
            idx += 1
        subjects_time_data.append(subject_timetable_data)
        subject_idx += 1

    return {
        "lecturers": lecturers_data,
        "subjects": subjects_data,
        "subjectsTime": subjects_time_data
    }

async def get_timetable_data(campus: str, semester: int, github_repo, file_name):
    timetable_data = fetch_data(campus, semester)
    file_contents = json.dumps(timetable_data)

    try:
        file = github_repo.get_contents(file_name, ref="main")
        existing_data = json.loads(file.decoded_content)

        # Compare the existing data with the new data
        if existing_data == timetable_data:
            print(f"No updates required for {file_name}.")
            return timetable_data

        github_repo.update_file(file.path, f"Update {file_name}", file_contents, sha=file.sha, branch="main")
    except GithubException as e:
        if e.status == 404:
            github_repo.create_file(file_name, f"Create {file_name}", file_contents, branch="main")
        else:
            raise e

    return timetable_data



async def main():
    # Get the latest semester codes
    latest_semester_codes = await get_latest_semester_codes(repo, "latest_semester_codes.json")

    # Print the latest semester codes for each campus
    for campus in ["SA", "BJ", "F"]:
        print(f"Latest semester codes for campus {campus}: {latest_semester_codes[campus]}")

    # Fetch the latest timetable data for each campus and semester
    tasks = []
    for campus in ["SA", "BJ", "F"]:
        for semester in latest_semester_codes[campus]:
            file_name = f"timetable_data_{semester}_{campus}.json"
            tasks.append(asyncio.create_task(get_timetable_data(campus, semester, repo, file_name)))

    await asyncio.gather(*tasks)
    print("Timetable data updated successfully for all semesters and campuses.")

# Run the main function
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
