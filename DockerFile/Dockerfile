FROM docker.io/rockylinux/rockylinux:9
MAINTAINER Strahil Nikolov <hunter86_bg@yahoo.com>
ENV USERNAME='myemail@example.com' \
    PASSWORD='mypass' \
    TADO_CHECK_INTERVAL='10.0' \
    TADO_ENABLE_LOG='False' \
    TADO_LOG_FILE='/var/log/tado.log' \
    TADO_TOKEN_FILE='/tmp/TADO_TOKEN_FILE' \
    HOME='/tmp'
RUN yum -y update && \
    yum -y install python3.12 python3.12-pip python3.12-requests git firefox jq && \
    yum clean all && \
    groupadd -g 1001 tado && \
    useradd -c "Tado user" -d $HOME -m -g tado -u 1001 -s /usr/bin/bash tado
RUN GECKO_VERSION=$(curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest | jq -r '.tag_name') && \
    curl -sL "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VERSION}/geckodriver-${GECKO_VERSION}-linux64.tar.gz" | \
    tar -xz -C /usr/bin && \
    chmod +x /usr/bin/geckodriver
WORKDIR $HOME
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/app.py", "./tado_aa.py" ]
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/requirements.txt", "./requirements.txt" ]
RUN chown -R tado:tado . && \
    # chmod 755 $HOME && \
    chmod 644 ${HOME}/tado_aa.py
RUN python3.12 -m pip install -r ./requirements.txt --no-cache-dir
USER tado
ENTRYPOINT ["/usr/bin/python3.12", "-u", "./tado_aa.py" ]
