#!/usr/bin/env python3
# -*- coding: utf-8 -*-

mqtt_host = 'mqtt.home'

import paho.mqtt.client as paho
import bme680
import time
import fcntl
from i2c_lock import i2c_lock, i2c_unlock

topic = '/sensor/desk'

def on_disconnect(mqtt, userdata, rc):
    print("Disconnected from MQTT server with code: %s" % rc)
    while rc != 0:
        try:
            time.sleep(1)
            rc = mqtt.reconnect()
        except:
            pass
        print("Reconnected to MQTT server.")

mqtt = paho.Client()
mqtt.connect(mqtt_host, 1883, 60)
mqtt.on_disconnect = on_disconnect
mqtt.loop_start()



try:
    while True:
        try:
            i2c_lock()
            sensor = bme680.BME680()
            sensor.set_humidity_oversample(bme680.OS_2X)
            sensor.set_pressure_oversample(bme680.OS_4X)
            sensor.set_temperature_oversample(bme680.OS_8X)
            sensor.set_filter(bme680.FILTER_SIZE_3)
            sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

            sensor.set_gas_heater_temperature(320)
            sensor.set_gas_heater_duration(150)
            sensor.select_gas_heater_profile(0)
            i2c_unlock()

            start_time = time.time()
            burn_in_time = 300
            burn_in_data = []
            gas_baseline = None

            # Set the humidity baseline to 50%, typical for my room
            hum_baseline = 50

            # This sets the balance between humidity and gas reading in the
            # calculation of air_quality_score (25:75, humidity:gas)
            hum_weighting = 0.25

            while True:
                i2c_lock()
                if sensor.get_sensor_data():
                    now = time.time()
                    timestamp = int(now)
                    mqtt.publish(topic + '/watchdog', 'reset', retain=False)
                    mqtt.publish(topic + '/humidity', sensor.data.humidity, retain=True)
                    mqtt.publish(topic + '/humidity/timestamp', timestamp, retain=True)
                    mqtt.publish(topic + '/pressure', sensor.data.pressure, retain=True)
                    mqtt.publish(topic + '/pressure/timestamp', timestamp, retain=True)
                    mqtt.publish(topic + '/temperature', sensor.data.temperature, retain=True)
                    mqtt.publish(topic + '/temperature/timestamp', timestamp, retain=True)

                    if now - start_time < burn_in_time:
                        if sensor.data.heat_stable:
                            gas = sensor.data.gas_resistance
                            burn_in_data.append(gas)
                        print("{}ºC\t{} %rH\t{} hPa".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure))
                        i2c_unlock()
                        time.sleep(1)

                    elif gas_baseline is None:
                        gas_baseline = sum(burn_in_data[-50:]) / 50.0
                        print("{}ºC\t{} %rH\t{} hPa".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure))
                        i2c_unlock()
                        time.sleep(1)

                    else:
                        if sensor.data.heat_stable:
                            gas = float(sensor.data.gas_resistance)
                            gas_offset = gas_baseline - sensor.data.gas_resistance
                            hum = sensor.data.humidity
                            hum_offset = sensor.data.humidity - hum_baseline

                            if hum_offset > 0:
                                hum_score = (100 - hum_baseline - hum_offset) / (100 - hum_baseline) * (hum_weighting * 100)
                            else:
                                hum_score = (hum_baseline + hum_offset) / hum_baseline * (hum_weighting * 100)
                            if gas_offset > 0:
                                gas_score = (gas / gas_baseline) * (100 - (hum_weighting * 100))
                            else:
                                gas_score = 100 - (hum_weighting * 100)

                            aq_score = hum_score + gas_score

                            mqtt.publish(topic + '/gas', gas, retain=True)
                            mqtt.publish(topic + '/gas/timestamp', timestamp, retain=True)
                            mqtt.publish(topic + '/aq', aq_score, retain=True)
                            mqtt.publish(topic + '/aq/timestamp', timestamp, retain=True)

                            print("{}ºC\t{} %rH\t{} hPa\t{} Ohms\t{}%".format(sensor.data.temperature, sensor.data.humidity, sensor.data.pressure, gas, aq_score))

                        i2c_unlock()
                        time.sleep(10)
                else:
                    print("No data yet.")
        except IOError as e:
            print("IOError: "+str(e))
            i2c_unlock()
            time.sleep(3)

except KeyboardInterrupt:
    pass
