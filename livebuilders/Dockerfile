ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV CLAUDE_CODE_USE_BEDROCK=0
COPY --chmod=644 protocol.py worker.py runtime.py /opt/livebuilders/
USER 1000:1000
ENTRYPOINT ["python3", "-u", "/opt/livebuilders/runtime.py"]
