# Motor

## Driver Pin

| BTS7960    | Arduino        | Function             |
|------------|---------------|----------------------|
| RPWM       | D5            | Motor Forward (PWM)  |
| LPWM       | D6            | Motor Backward (PWM) |
| R_EN       | D7            | Enable Forward       |
| L_EN       | D8            | Enable Backward      |
| VCC        | 5V            | Power for logic      |
| GND        | GND           | Ground               |
| MOTOR+     | Motor Red (+) | Power Output         |
| MOTOR-     | Motor Black (-)| Power Output        |
| B+ & B-    | 24V DC Supply | Motor Power          |

## Encoder Pin

| Encoder Pin | Arduino | Function           |
|-------------|---------|--------------------|
| CHA         | D2      | Encoder Signal A   |
| CHB         | D3      | Encoder Signal B   |
| VCC         | 5V      | Power for Encoder  |
| GND         | GND     | Ground             |

## Limit Switch

| Limit Switch | Arduino Pin | Common Pin |
|--------------|-------------|------------|
| Kanan        | D9          | GND        |
| Kiri         | D10         | GND        |

## Rotary Switch

| Rotary Switch Pin | Arduino Pin |
|-------------------|-------------|
| VCC               | VCC         |
| 1                 | 12          |
| 2                 | 13          |
| 3                 | 14          |
| 4                 | 15          |
| 5                 | 16          |
| 6                 | 17          |