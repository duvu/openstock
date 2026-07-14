# Installation and preparation

<figure><img src="/files/ll4cukib6lzGJ5g1BRfH" alt=""><figcaption></figcaption></figure>

### 1. Installing Python on Windows 🖥️

Install from Python.org (Recommended)

{% stepper %}
{% step %}
**📌  Download Python**

&#x20;Access [Python Homepage](https://www.python.org/downloads/windows/)&#x20;

Click Download Python (Latest version)
{% endstep %}

{% step %}
**📌 Install Python**

Open the downloaded .exe file.

Click “Add Python to PATH”

Click "Install Now" and wait for the installation process to complete.
{% endstep %}

{% step %}
**📌** Verify installation

Open Command Prompt (CMD) and type:

```
python --version
```

{% endstep %}
{% endstepper %}

### 2. Install FiinQuant library. <a href="#cai-dat-thu-vien-fiinquant" id="cai-dat-thu-vien-fiinquant"></a>

```
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

Update library when a new version is available.

```
pip install --upgrade --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

Note: <mark style="color:red;">**DO NOT NAME YOUR PYTHON SCRIPT FILES THE SAME AS THE LIBRARY (i.e., FiinQuant).**</mark>\ <br>
