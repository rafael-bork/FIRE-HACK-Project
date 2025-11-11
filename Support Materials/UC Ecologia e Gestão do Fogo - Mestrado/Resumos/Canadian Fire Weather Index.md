#FEM

**Fire Danger** describes the assessment of both the static and dynamic factors of the fire environment which determine the ease of ignition, rate of spread, difficulty of control and severity of fire effects.

The **Canadian FWI** provides a means of evaluating the danger and severity of a fire by aggregating ratings of **[[Fuel Particle Moisture|fuel moisture]]** in these codes for the 3 fuel size classes:
- **[[Canadian Fire Weather Indices#Fine Fuel Moisture Code|Fine Fuel Moisture Code]]**
- **[[Canadian Fire Weather Indices#Duff Moisture Code|Duff Moisture Code]]**
- **[[Canadian Fire Weather Indices#Drought Code|Drought Code]]**


This indices are derived from the previous days' values and once a day measurements, taken at 13:00h, of:
- Air Temperature
- Relative Humidity
- Wind Speed
- 24h Accumulated Precipitation

It is based on a simple and generally applicable **[[Fuel Particle Moisture#Fuel Drying|moisture exchange model]]** where the moisture variation in each fuel layer follows an exponential curve towards an equilibrium moisture value. (It doesn't use [[Fuel Models|regressional/empirical corelations]] because they were very local and the results were not very accurate in areas different from the original training data)

This equilibrium moisture value and the response time of moisture exchange is determined mathematically by the previously mentioned **weather measurements** and the **previous days' moisture values**. 

The system doesn't take into account the differences in forest type, it is used in a common standardized forest type.


![[FireWeatherIndex.png]]

The remaining three fire behaviour codes are created from the moisture codes and represent relative ratings of fire behaviour potential, capturing:
- **[[Canadian Fire Weather Indices#Initial Spread Index|Initial Spread Index]]** -> fire spread rate
- **[[Canadian Fire Weather Indices#Built-Up Index|Build-Up Index]]** -> fuel consumption 
- **[[Canadian Fire Weather Indices#Fire Weather index|Fire Weather Index]]** -> fireline intensity

The **[[Canadian Fire Weather Indices#Daily Severity Rating|Daily Severity Rating]]** (DSR) is a transformation of the Fire Weather Index (FWI) that is used for averaging daily fire danger into monthly or seasonal values.


