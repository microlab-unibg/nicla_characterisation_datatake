#include "Nicla_System.h"
#include "Arduino_BHY2.h"
#include <ArduinoBLE.h>

SensorBSEC2Collector bsec2Collector(SENSOR_ID_BSEC2_COLLECTOR);

#define CONFIG_BSEC2_USE_DEAULT_HP 1

#if CONFIG_BSEC2_USE_DEAULT_HP
// Default Heater temperature and time base(Recommendation)
const uint16_t BSEC2HP_TEMP[] = {320, 100, 100, 100, 200, 200, 200, 320, 320, 320}; // HP-354 / 
const uint16_t BSEC2HP_DUR[] = {5, 2, 10, 30, 5, 5, 5, 5, 5, 5};  // the duration in steps of 140ms, 5 means 700ms, 2 means 280ms
#else
// customized Heater temperature and time base
const uint16_t BSEC2HP_TEMP[] = {100, 320, 320, 200, 200, 200, 320, 320, 320, 320}; // HP-321 / 
const uint16_t BSEC2HP_DUR[] = {43, 2, 2, 2, 21, 21, 2, 14, 14, 14};  // the duration in steps of 140ms, 5 means 700ms, 2 means 280ms
#endif

#define BLE_SENSE_UUID(val) ("19b10000-" val "-537e-4f6c-d104768a1214")
#define ACQUISITION_INTERVAL 5000
#define SCAN_INTERVAL 1000

// Constants
const int VERSION = 0x00000000;

// BLE variables
BLEService service(BLE_SENSE_UUID("0000"));

BLEUnsignedIntCharacteristic versionCharacteristic(BLE_SENSE_UUID("1001"), BLERead | BLENotify);
BLEFloatCharacteristic temperatureCharacteristic(BLE_SENSE_UUID("2001"), BLERead | BLENotify);
BLEFloatCharacteristic humidityCharacteristic(BLE_SENSE_UUID("3001"), BLERead | BLENotify);
BLEFloatCharacteristic pressureCharacteristic(BLE_SENSE_UUID("4001"), BLERead | BLENotify);

BLEUnsignedIntCharacteristic accelerometerCharacteristic(BLE_SENSE_UUID("5001"), BLERead | BLENotify, 3 * sizeof(float));  // Array of 3x 2 Bytes, XY
BLEUnsignedIntCharacteristic gyroscopeCharacteristic(BLE_SENSE_UUID("6001"), BLERead | BLENotify, 3 * sizeof(float));      // Array of 3x 2 Bytes, XYZ
BLEUnsignedIntCharacteristic quaternionCharacteristic(BLE_SENSE_UUID("7001"), BLERead | BLENotify, 4 * sizeof(float));     // Array of 4x 2 Bytes, XYZW

BLECharacteristic rgbLedCharacteristic(BLE_SENSE_UUID("8001"), BLERead | BLEWrite, 3 * sizeof(byte));  // Array of 3 bytes, RGB

BLEUnsignedIntCharacteristic bsecCharacteristic(BLE_SENSE_UUID("9001"), BLERead | BLENotify);
BLEUnsignedLongCharacteristic co2Characteristic(BLE_SENSE_UUID("9002"), BLERead | BLENotify);
BLEFloatCharacteristic gasCharacteristic(BLE_SENSE_UUID("9003"), BLERead | BLENotify);
BLEUnsignedShortCharacteristic accuracyCharacteristic(BLE_SENSE_UUID("9004"), BLERead | BLENotify);

// String for the local and device name
String name;

// Sensor declarations
Sensor temperature(SENSOR_ID_TEMP);
Sensor humidity(SENSOR_ID_HUM);
Sensor pressure(SENSOR_ID_BARO);
Sensor gas(SENSOR_ID_GAS);
SensorXYZ gyroscope(SENSOR_ID_GYRO);
SensorXYZ accelerometer(SENSOR_ID_ACC);
SensorQuaternion quaternion(SENSOR_ID_RV);
SensorBSEC bsec(SENSOR_ID_BSEC);

// values from sensors
float gyroscopeValues[3];
float accelerometerValues[3];

// variable to be to check for time to be passed
unsigned long last_acq_time;
unsigned long last_scan_time;

// To take care of central
bool central_discovered;
BLEDevice central;

void setup() {
  Serial.begin(115200);

  Serial.println("Start");

  nicla::begin();
  nicla::leds.begin();
  nicla::leds.setColor(red);

  //Sensors initialization
  BHY2.begin(NICLA_STANDALONE);
  sensortec.bhy2_bsec2_setHP((uint8_t*)BSEC2HP_TEMP, sizeof(BSEC2HP_TEMP), (uint8_t*)BSEC2HP_DUR, sizeof(BSEC2HP_DUR)); 

  accelerometer.begin(100, 0);
  accelerometer.setRange(8);
  gyroscope.begin(100, 0);
  gyroscope.setRange(2000);
  temperature.begin(1, 0);
  humidity.begin(1, 0);
  pressure.begin(1, 0);
  bsec.begin(1, 0);
  quaternion.begin(100, 0);
  gas.begin(1, 0);

  if (!BLE.begin()) {
    Serial.println("Failed to initialize BLE!");
    while (1)
      ;
  }

  String address = BLE.address();

  Serial.print("address = ");
  Serial.println(address);

  address.toUpperCase();

  name = "NiclaSenseME-";
  name += address[address.length() - 5];
  name += address[address.length() - 4];
  name += address[address.length() - 2];
  name += address[address.length() - 1];

  Serial.print("name = ");
  Serial.println(name);

  BLE.setLocalName(name.c_str());
  BLE.setDeviceName(name.c_str());
  BLE.setAdvertisedService(service);

  // Add all the previously defined Characteristics
  service.addCharacteristic(temperatureCharacteristic);
  service.addCharacteristic(humidityCharacteristic);
  service.addCharacteristic(pressureCharacteristic);
  service.addCharacteristic(versionCharacteristic);
  service.addCharacteristic(accelerometerCharacteristic);
  service.addCharacteristic(gyroscopeCharacteristic);
  service.addCharacteristic(quaternionCharacteristic);
  service.addCharacteristic(bsecCharacteristic);
  service.addCharacteristic(co2Characteristic);
  service.addCharacteristic(gasCharacteristic);
  service.addCharacteristic(accuracyCharacteristic);
  service.addCharacteristic(rgbLedCharacteristic);

  rgbLedCharacteristic.setEventHandler(BLEWritten, onRgbLedCharacteristicWrite);

  versionCharacteristic.setValue(VERSION);

  BLE.addService(service);
  BLE.advertise();

  central_discovered = false;
  BLEDevice central;

  last_scan_time = 0;
  last_acq_time = 0;
}

void loop() {
  if (!central_discovered) {
    if (millis() - last_scan_time > SCAN_INTERVAL) {
      last_scan_time = millis();
      // Scan every SCAN_INTERVAL ms
      // Search for a central
      nicla::leds.setColor(yellow);
      central = BLE.central();
      Serial.println("Scanning for central device...");

      if (central) {
        central_discovered = true;
        Serial.println("Central device found and connected! Device MAC address: ");
        Serial.println(central.address());
      }
    } else nicla::leds.setColor(red);
  } else {
    if (millis() - last_acq_time > ACQUISITION_INTERVAL) {
      last_acq_time = millis();
      // Comms every ACQUISITION_INTERVAL ms
      if (central) {
        if (central.connected()) {
          nicla::leds.setColor(blue);
          BHY2.update();

          check_subscriptions();
        }
      } else {
        central_discovered = false;
      }
    } else {
      nicla::leds.setColor(green);

      if (!central.connected()) {     
        central_discovered = false;        
      } 
    }
  }
}

void check_subscriptions() {
  if (temperatureCharacteristic.subscribed()) {
    temperature_notify();              
  }
  if (humidityCharacteristic.subscribed()) {
    humidity_notify();              
  }
  if (pressureCharacteristic.subscribed()) {
    pressure_notify();              
  }
  if (accelerometerCharacteristic.subscribed()) {
    accelerometer_notify();              
  }
  if (gyroscopeCharacteristic.subscribed()) {
    gyroscope_notify();              
  }
  if (quaternionCharacteristic.subscribed()) {
    quaternion_notify();              
  }
  if (bsecCharacteristic.subscribed()) {
    bsec_notify();              
  }
  if (co2Characteristic.subscribed()) {
    co2_notify();              
  }
  if (gasCharacteristic.subscribed()) {
    gas_notify();              
  }
  if (accuracyCharacteristic.subscribed()) {
    accuracy_notify();              
  }
}

void accelerometer_notify() {
  uint16_t accelerometerValues[] = { accelerometer.x(), accelerometer.y(), accelerometer.z() };
  accelerometerCharacteristic.writeValue(accelerometerValues, sizeof(accelerometerValues));
}

void gyroscope_notify() {
  uint16_t gyroscopeValues[] = { gyroscope.x(), gyroscope.y(), gyroscope.z() };
  gyroscopeCharacteristic.writeValue(gyroscopeValues, sizeof(gyroscopeValues));
}

void quaternion_notify() {
  uint16_t quaternionValues[] = { quaternion.x(), quaternion.y(), quaternion.z(), quaternion.w() };
  quaternionCharacteristic.writeValue(quaternionValues, sizeof(quaternionValues));
}

void temperature_notify() {
  float temperatureValue = temperature.value();
  temperatureCharacteristic.writeValue(temperatureValue);
}

void humidity_notify() {
  float humidityValue = humidity.value();
  humidityCharacteristic.writeValue(humidityValue);
}

void pressure_notify() {
  float pressureValue = pressure.value();
  pressureCharacteristic.writeValue(pressureValue);
}

void bsec_notify() {
  uint16_t airQuality = float(bsec.iaq());
  bsecCharacteristic.writeValue(airQuality);
}

void co2_notify() {
  uint32_t co2 = bsec.co2_eq();
  co2Characteristic.writeValue(co2);
}

void gas_notify() {
  float g = gas.value();
  gasCharacteristic.writeValue(g);
}

void accuracy_notify() {
  uint8_t a = int(bsec.accuracy());
  accuracyCharacteristic.writeValue(a);
}

void onRgbLedCharacteristicWrite(BLEDevice central, BLECharacteristic characteristic) {
  byte r = rgbLedCharacteristic[0];
  byte g = rgbLedCharacteristic[1];
  byte b = rgbLedCharacteristic[2];

  nicla::leds.setColor(r, g, b);
}
