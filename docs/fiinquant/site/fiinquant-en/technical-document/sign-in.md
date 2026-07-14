# Sign in

**Managing login sessions**

| Parameter | Description |
| --------- | ----------- |
| username  | User's ID   |
| password  | ID password |

**Method**

| Method name         | Error code | Description                      |
| ------------------- | ---------- | -------------------------------- |
| User does not exist | 400        | User entered incorrect username. |
| Incorrect password  | 400        | User entered incorrect password. |

**Assess login session**

```python
import FiinQuantX as fq


username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(
    username=username,
    password=password,
).login()
```
