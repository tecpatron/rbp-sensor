#include <LiquidCrystal.h>
#include "DHT.h"

#define DHTPIN 7
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

int ledAzul = 8;
int ledRojo = 9;

// Límites iniciales
float tMin = 18;
float tMax = 26;
float hMin = 30;
float hMax = 60;

void setup() {
  Serial.begin(9600);
  dht.begin();
  lcd.begin(16, 2);

  pinMode(ledAzul, OUTPUT);
  pinMode(ledRojo, OUTPUT);

  lcd.print("Iniciando...");
  delay(2000);
}

void loop() {

  recibirLimites();

  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t) || h < 1 || h > 100 || t < 1 || t > 60) {
    lcd.clear();
    lcd.print("Lectura invalida");
    digitalWrite(ledRojo, HIGH);
    digitalWrite(ledAzul, LOW);
    delay(1000);
    return;
  }

  // Mostrar en LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Temp: ");
  lcd.print(t);
  lcd.print(" C");

  lcd.setCursor(0, 1);
  lcd.print("Hume: ");
  lcd.print(h);
  lcd.print(" %");

  // Envia los datos a Python
  Serial.print(t);
  Serial.print(",");
  Serial.println(h);

  bool tempOK = (t >= tMin && t <= tMax);
  bool humOK  = (h >= hMin && h <= hMax);

  if (tempOK && humOK) {
    digitalWrite(ledAzul, HIGH);
    digitalWrite(ledRojo, LOW);
  } 
  else {
    digitalWrite(ledRojo, HIGH);
    digitalWrite(ledAzul, LOW);
  }

  delay(1500);
}

void recibirLimites() {

  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');

    if (comando.startsWith("SET")) {
      float newTmin, newTmax, newHmin, newHmax;

      sscanf(comando.c_str(), "SET %f %f %f %f", 
             &newTmin, &newTmax, &newHmin, &newHmax);

      tMin = newTmin;
      tMax = newTmax;
      hMin = newHmin;
      hMax = newHmax;

      Serial.println("OK");
    }
  }
}
