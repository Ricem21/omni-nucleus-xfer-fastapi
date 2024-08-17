FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10

RUN apt-get update
#RUN apt-get install -y python-dev python-pip libffi-dev libssl-dev
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./omni-client /opt/omni-client
WORKDIR /opt/omni-client
RUN tar -xvf connect-samples-205.0.0.tar.gz
WORKDIR /opt/omni-client/connect-samples-205.0.0
RUN ./build.sh

ENV SCRIPT_DIR=/opt/omni-client/connect-samples-205.0.0
ENV USD_LIB_DIR=${SCRIPT_DIR}/_build/linux-x86_64/release
ENV LD_LIBRARY_PATH=${USD_LIB_DIR}
ENV PYTHONPATH=/app:${USD_LIB_DIR}/python:${USD_LIB_DIR}/bindings-python

COPY ./data /tmp
COPY ./app /app

