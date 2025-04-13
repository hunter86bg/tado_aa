FROM docker.io/library/python:latest
MAINTAINER Strahil Nikolov <hunter86_bg@yahoo.com>
ENV USERNAME='myemail@example.com' \
    PASSWORD='mypass' \
    TADO_CHECK_INTERVAL='10.0' \
    TADO_ENABLE_LOG='False' \
    TADO_LOG_FILE='/var/log/tado.log' \
    HOME='/tado'
RUN yum -y update && \
    yum -y install python3-pip python3-requests git && \
    yum clean all && \
    groupadd -g 1001 tado && \
    useradd -c "Tado user" -d $HOME -m -g tado -u 1001 -s /usr/bin/bash tado
WORKDIR $HOME
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/app.py", "./tado_aa.py" ]
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/requirements.txt", "./requirements.txt" ]
RUN chown -R tado:tado . && \
    chmod 755 $HOME && \
    chmod 644 ${HOME}/tado_aa.py
RUN python3 -m pip install -r ./requirements.txt --no-cache-dir
USER tado
ENTRYPOINT ["/usr/bin/python3", "-u", "./tado_aa.py" ]
