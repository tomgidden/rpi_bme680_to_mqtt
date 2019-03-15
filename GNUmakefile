TAG=tomgidden/rpi_bme680_to_mqtt


start:
	docker create --device /dev/i2c-1 --name bme680_to_mqtt  $(TAG)
	docker start bme680_to_mqtt

stop:
	docker rm -f bme680_to_mqtt

build: Dockerfile *.py requirements.txt
	docker build . -t $(TAG)

push:
	docker push $(TAG):latest

test:
	docker run -it --rm --privileged -v /dev/i2c-1:/dev/i2c-1 $(TAG) bash
