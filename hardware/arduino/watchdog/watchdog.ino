// Watchdog Arduino – Securite robot Inspecteur Pixel OS
// Recoit un heartbeat du GPU via Serial.
// Si le heartbeat est perdu > 100ms, coupe les moteurs.

const int MOTOR_PIN = 9;          // Pin de commande moteur (exemple)
const unsigned long TIMEOUT = 100; // ms avant coupure
const int LED_PIN = LED_BUILTIN;

unsigned long lastHeartbeat = 0;
bool motorsEnabled = false;

void setup() {
    pinMode(MOTOR_PIN, OUTPUT);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(MOTOR_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    Serial.begin(115200);
    lastHeartbeat = millis();
}

void loop() {
    // Verifier la reception du heartbeat
    if (Serial.available()) {
        char c = Serial.read();
        if (c == 'H') {
            lastHeartbeat = millis();
            if (!motorsEnabled) {
                motorsEnabled = true;
            }
            Serial.println("ACK");   // repondre au GPU
            digitalWrite(LED_PIN, HIGH);
        }
    }

    // Verifier le timeout du heartbeat
    if (millis() - lastHeartbeat > TIMEOUT) {
        // Perte de communication : arret d'urgence
        digitalWrite(MOTOR_PIN, LOW);
        digitalWrite(LED_PIN, LOW);
        motorsEnabled = false;
        Serial.println("ERR");      // signaler l'erreur

        // Boucle jusqu'a reception d'un nouveau heartbeat
        while (true) {
            if (Serial.available() && Serial.read() == 'H') {
                lastHeartbeat = millis();
                motorsEnabled = true;
                digitalWrite(MOTOR_PIN, HIGH);
                digitalWrite(LED_PIN, HIGH);
                Serial.println("ACK");
                break;
            }
            delay(1);
        }
    }

    // Si tout va bien, le moteur peut etre active
    // (la logique normale decide quand activer)
    // digitalWrite(MOTOR_PIN, HIGH);
    delay(1);
}
