# Common errors

1. ### ImportError

<figure><img src="/files/fwg9VDRc8gJhMXdL0NX7" alt=""><figcaption><p>Import Error</p></figcaption></figure>

**Reason 11:**

Windows Defender might delete or quarantine the file, so users need to restore it before running the code again.

How to restore the file from Quarantine:

1. Open **Windows Security** by pressing **Win + S**, type “Windows Security,” then open the application.
2. Go to “**Virus & threat protection**.”
3. Click “**Protection history**.”
4. Find the “**Threat quarantined**” entry related to `FiinQuant\__init__.py`.
5. Click “**Actions**” → Select “**Restore**.”

🔹 **Note:** If Windows Defender automatically deletes the file, you need to reinstall the FiinQuant library after restoring it.
