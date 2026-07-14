# Retrieve and save real-time data to Google Sheet

## Create and download Google JSON service account key

Access Google Cloud Console: <https://console.cloud.google.com/>

Select or create a new project; if no project exists, click "New Project."

<figure><img src="/files/Z49VincTfBth7zggDULW" alt=""><figcaption></figcaption></figure>

Access **APIs & Services > Library**

<figure><img src="/files/gf3V0bRZuh6tXXmTULM3" alt=""><figcaption></figcaption></figure>

<figure><img src="/files/GLozvc66M7s9OVOSSG6y" alt=""><figcaption></figcaption></figure>

Click **Google Sheets API**

<figure><img src="/files/w8H5dfVhaONPSb1a2AWx" alt=""><figcaption></figcaption></figure>

Enable API

<figure><img src="/files/sDzeKFH6s0aQ9rStCBfM" alt=""><figcaption></figcaption></figure>

Access **IAM & Admin > Service Accounts**, click **"Create Service Account"**, perform naming for the Service Account, then click "Create and Continue".

<figure><img src="/files/UF1NI0MVcI8UgCd59Zbh" alt=""><figcaption></figcaption></figure>

Choose a role for Service Account (Editor) and click "Continue".

<figure><img src="/files/4eOilJoWXGvKbNBVLQYR" alt=""><figcaption></figcaption></figure>

After creating the Service Account, click on the newly created Service Account name, go to the "**Keys**" tab, click "**Add Key**" > "**Create new key**", select **JSON**, and click "**Create**." Your browser will then download the JSON configuration file to automatically access Google Sheets. Next, move the downloaded JSON file to the same folder as your Python file where you write the code to retrieve data from FiinQuant and save it to Google Sheets.
