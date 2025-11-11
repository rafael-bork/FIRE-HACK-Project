#FEM 
Fire modelling deals with mathematical simulation of wildland fires to understand and predict their [[Fire Behavior Metrics|behavior variables]]: 
- rate of spread, 
- fire intensity, 
- likelihood of a surface fire turning into a canopy fire, 
- if the fire behavior dominated by wind or a convection column,
- tree mortality
- effect on vegetation, soils, water and atmosphere
- etc.


## Rothermel's fire spread model
This model describes the balance between how much energy is released by the fire and how much energy is spent heating up the fuels to their ignition point.

The application of Rothermel’s fire spread model assumes fuel horizontal continuity, fuel model uniformity, fuel height less than 2m, and steady-state fire behavior conditions. 
(the model as originally designed was inappropriate to deal with smoldering and glowing combustion, crown fires, spotting and ignition of secondary fires, fire whirls, and prescribed burns).

### Fire Rate of Spread
The basic concept of Rothermel’s fire model is very simple. The fire rate of spread, $r$, is given by the ratio between a heat source and a heat sink:
$$r=\frac{heat\ source}{heat\ sink}\ (m/min)$$
#### Heat Source
The heat source numerator represents the rate of heat generated per unit fuelbed area burned.
$$heat\ source = I_R\ \xi\ (1+\phi_w+\phi_s)\ (kJ/min\ m^2)$$
##### Reaction Intensity, $I_R\ (kJ/min\ m^2)$
Rate of heat release in the flame front per unit fuelbed area. 
Increases with fuel load and heat content; decreases with increasing bulk density and moisture content.
$$I_R=\Gamma'\ w_n\ h\ (kJ/min\ m^2)$$
$\Gamma'$ - **Reaction velocity** $(min^{-1})$, The rate at which fuel is consumed in the flaming zone. It is a function of the **fuelbed packing ratio**, $\beta$, the particles **surface-to-volume ratio**, $\sigma$, and empirical parameters.
$w_n$ - **Consumed fuel load** $(kg/m^2)$, The amount of available fuel that actually burns.
$h$ - **Fuel heat content** $(kJ/kg)$, The amount of heat released per unit mass of fuel when it burns.
##### Propagating flux ratio $\xi\ ()$
Proportion of the reaction intensity that contributes to forward fire spread by heating the adjacent fuel.
Normally $I_R$ heat is lost to the atmosphere, such that $\xi<0.2$ .
##### Wind Factor $\phi_w\ ()$   
The effect of wind in the increase of the propagating flux ratio, $\xi$, as a function of **wind speed** and **surface-to-volume ratio**, $\sigma$. 
When wind increases, a larger fraction of $I_R$ is transferred to fuels ahead of the flaming front, therefore $\phi_w$ is greater.
If the wind speed reaches 50km/h the fire's convection system is slowed and the fires' intensity plateaus.
##### Slope Factor $\phi_s\ ()$ 
The effect of slope in the increase of the propagating flux ratio, $\xi$, as a function of **slope steepness** and **bulk density**, $\rho_b$. 
When slope increases, a larger fraction of $I_R$ is transferred to fuels ahead of the flaming front, therefore $\phi_s$ is greater.


#### Heat sink
The heat sink denominator represents the heat required to raise to ignition temperature a unit volume of fuelbed.
$$heat\ sink=\rho_b\ \varepsilon\ Q_{ig}\ (kJ/m^3)$$
##### Bulk Density $\rho_b\ (kg/m^3)$
A measure of fuelbed compactness and density,
##### Effective heating number $\varepsilon\ ()$ 
The fraction of the total fuel load that must be heated to ignition for it to start.
Particles with lower **surface-to-volume ratio**, $\sigma$, need to be totally heated to ignition temperature ($\varepsilon \approx 1$) while particles with higher surface-to-volume ratios only need their outer portion to be heated to ignition ($\varepsilon \ll1$)
##### Heat of Ignition $Q_{ig}\ (kJ/kg)$
The amount of energy required to heat a given mass of fuel to its ignition temperature. 
It is a function of **moisture content**, because the it must be vaporized firstly, before raising the fuel's temperature to ignition.


For the calculations of the variables' values, were developed empirical equations, based on fuel model parameters. in order to give the model its predictive ability: we can predict the fire behavior based on predefined fuel models, combined with observed or hypothetical meteorological and topographic data

