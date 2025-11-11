
### Rate of Spread
A active crown fire's rate of spread depends on the balance between the speed at which fire must advance and the amount of crown fuel it consumes, it will stop spreading if the heat flux from the flame front is too low, or if the heat required to ignite the fuels is too high. Therefore the rate of fire spread, , is:
$$r_{active} = \frac{E}{\rho_b\ Q_{ig}}\ (m/s)$$
##### Heat Flux $E\ (kW/m^2)$
Heat flux per unit canopy area required for sustained crown fire spread.

##### Canopy Layer Bulk Density $\rho_b\ (kg/m^3)$
A measure of canopy fuel layer compactness and density.

##### Heat of Ignition $Q_{ig}\ (kJ/kg)$
The amount of energy required to heat a given mass of fuel to its ignition temperature. 

We can rearrange the equation in such way: $\frac{E}{Q_{ig}}=r_{active}\ \rho_b$
So that we can replace $\frac{E}{Q_{ig}}$ by a new term $S$, therefore $$S=r_{active}\ \rho_b$$
##### Mass Flow Rate $S$ $kg/m^2\ s$
The rate of fuel consumption in the flame front through a vertical plane parallel to the flame front.
This value must surpass a threshold $(S_0)$ for the crown fire to spread, if this is not the case, we only see a surface fire. This value determined in experimental crown fires is $0.05\ kg/m^2\ s$

#### Rate of Spread Critical Value $r'_{active}$ $m/s$
The rate of spread, $r_{active}$, can also be expressed as a critical value, $r'_{active}$, meaning that there is a rate of spread value below which fire no longer spreads through the forest crowns.
$$r'_{active}=\frac{S_0}{\rho_b}=\frac{0.05}{\rho_b}$$
This relation does not predict the rate of crown fire spread. It identifies the combinations of rate of spread and canopy bulk density for which an active crown fire is possible.



### Transition Criteria
Surface fire intensity, $I_{survace}$, has to exceed a minimum threshold, $I'_{initiation}$ , $(kW/m)$ for a surface fire to ignite the tree crowns.
$$I'_{iniciation}=(C\ Q_{ig}\ CBH)^{1.5}=[0.01\ (460+26FMC)\ CBH]^{1.5}$$

##### Constant $C$
Empirical constant estimated in experimental crown fires.

##### Heat of Ignition $Q_{ig}\ (kJ/kg)$
The amount of energy required to heat a given mass of crown fuel to its ignition temperature. 

##### Folicular Moisture Content $FMC$ $(\%)$
Leaf moisture content of crown foliage.

##### Crown Base Height $CBH$ $(m)$
Crown base height of the canopy.


## Predicting Crown Fires
We can now quantitatively defined the various types of fire behavior: If $I_{survace}<I'_{survace}$                                      -> **Surface Fire**
If $I_{survace}>I'_{survace}$ and $R_{active}<R'_{active}$     -> **Passive Crown Fire**
If $I_{survace}>I'_{survace}$ and $R_{active}>R'_{active}$     -> **Active Crown Fire**

![[CrownFirePrediction.png|300]]


## Wind-Driven Crown Fires
### Rate of Spread $r$ $(m/s)$
The model states that the mean rate of spread for the experimental crown fires used to develop it was 3.34 times faster than that predicted for the surface fire.
$$r_{active}=3.34\ (r_{10})_{WAF\ 0.4}$$

##### Rate of Spread in fuel model 10 $r$ $(m/s)$
Predicted rate of spread of surface fire in fuel model 10 (timber litter and understory)

##### Wind Attenuation Factor of 0.4 $WAF\ 0.4$
Wind speed in the forest understory is reduced to 40% of the wind speed out in the open due to presence of the forest canopy.


This moderately accurate model allows quantitative assessment of crown fire hazard.


### Torching Index $TI$
The open windspeed , $O'_{initiation}$ at which $r_{surface}$ exceeds $r_{initiation}$ (same as $I_{surface}$ > $I_{initiation}$).

### Crowning Index $CI$
The open windspeed , $O'_{active}$ at which $r_{active}$ exceeds $r'_{active}$.

A **Surface Fire** is expected at windspeeds below TI. 
Windspeeds greater than TI but less than CI lead to **Passive Crowning**.
**Active Crown Fire** is expected at windspeeds above CI. 

The higher the windspeed value required to initiate (TI) and spread (CI) fire through the crowns, the lower the fire potential, and the less vulnerable to fire is the forest.

![[CrownFireAssessment.png]]

Inputs: fuel model 10 (timber litter and understory), canopy base height = 1.5 m, canopy bulk density = 0.15 kg m-3, foliar moisture content = 100 percent, normal summer surface fuel moisture condition, and wind reduction factor = 0.15.


![[SurfacetoCrownFireMetrics.png]]
The vertical jump in the conifer forest curves represents the point of surface-to-crown fire transition, where there is a sudden increase in quantity of fuel load available and, therefore, fire intensity and rate of spread



The purpose of crown fire behavior simulations is to assess the relative fire potential in forest stands, not to predict the behavior of an actual fire.
