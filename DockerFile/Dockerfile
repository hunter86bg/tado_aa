FROM docker.io/rockylinux/rockylinux:9
MAINTAINER Strahil Nikolov <hunter86_bg@yahoo.com>
ENV USERNAME 'myemail@example.com'
ENV PASSWORD 'mypass'
ENV TADO_CHECK_INTERVAL '10.0'
ENV TADO_ENABLE_LOG 'False'
ENV TADO_LOG_FILE '/var/log/tado.log'
ENV HOME '/tado'
RUN yum -y update && \
yum -y install python3-pip python3-requests && \
yum clean all && \
groupadd -g 1001 tado && \
useradd -c "Tado user" -d $HOME -m -g tado -u 1001 -s /usr/bin/bash tado
WORKDIR $HOME
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/app.py", "${HOME}/tado_aa.py" ]
ADD [ "https://raw.githubusercontent.com/hunter86bg/tado_aa/master/requirements.txt", "${HOME}/requirements.txt" ]
RUN chown -R tado:tado $HOME
USER tado
RUN python3 -m pip install -r ${HOME}/requirements.txt --user --no-cache-dir
ENTRYPOINT ["/usr/bin/python3", "-u", "./tado_aa.py" ]
