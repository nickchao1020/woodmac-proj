docker-build:
	docker build -t woodmac-eia-report-generator .

docker-run:
	docker run \
		-p 8501:8501 \
		-v $(shell pwd)/outputs:/app/outputs \
		-e EVENTS_DIR=/app/outputs \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_REGION=$(AWS_REGION) \
		-e BEDROCK_INFERENCE_PROFILE_ARN=$(BEDROCK_INFERENCE_PROFILE_ARN) \
		woodmac-eia-report-generator
