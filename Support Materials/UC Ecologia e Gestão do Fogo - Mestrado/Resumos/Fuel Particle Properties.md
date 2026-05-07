#FEM #FEM/Properties 
### Particle Diameter ($d$)
Different particle diameter classes play distinct roles in the combustion and fire spread processes ($cm$).
It is assumed that fuel particles have simple geometric shapes, like cylinders for branches and needles, and thin plates for broad leaves.

Particle diameter is divided into four size classes: 
- < 0.6 cm, 
- 0.6 – 2.5 cm, 
- 2.5 – 7.5 cm,
- 7.5 cm.

Small fuels dry out rapidly and respond more quickly to short-term variability in ambient RH, while large fuels require much longer dry periods to reach similar dryness.


### Surface-to-Volume Ratio ($\sigma$)
It is defined as the area of a particle surface divided by the volume of that particle.
$$ \sigma = \frac{A}{V}\ (m^3\ or\ cm^3) $$

It is often indirectly estimated from particle diameter (d), using the equations:
- $\sigma = 4/d$  for cylindrical objects
- $\sigma=2/t$ for plates with $t$ thickness

Thick particles, such as logs, have low $\sigma$, while thin particles, like grass blades or pine needles have high $\sigma$.

For the same object shape, an increase in size reduces the surface-to-volume ratio. And therefore, if the shape is cut up into various parts, the surface-to-volume ratio will be higher.

A larger object has a smaller $\sigma$ through which to exchange mass (e.g. water) and energy (e.g. radiant heat), thus, it will take longer to moisten up/dry out, and to heat up/cool down than a smaller object.

The average $\sigma$ for wood is $512km/m^3$.


### Particle Density ($\rho_p$)
Particle density is the dry weight of the particle per unit volume.
$$\rho_p=\frac{m}{V}\ (kg/m^3)$$
#### Specific Gravity
$$1\ specific\ gravity=1000\ kg/m^3$$


### Mineral Content
Mineral content has a profound impact on fire behaviour.

#### Total Mineral Content ($S_T$)
The total mineral content is the percent of the weight per unit volume of fuel particle that is inorganic material or mineral (i.e., not composed of molecules of C, H, and O)
$$S_T=\frac{m_{inorganic}}{m_{total}}\ (\%)$$

### Effective Mineral Content ($S_e$)
Effective mineral content ( Se) is the mineral content with the proportion of silica removed because it does not have an impact on the combustion (silica is inert).
$$S_T=\frac{m_{inorganic}-m_{silica}}{m_{total}}\ (\%)$$

Ground fuels usually have the highest mineral contents, often greater than 10%, that's why ground fuels mostly burn in smouldering combustion, without flames.


## Heat Content ($h$)
The heat content is the energy released by the combustion of one unit mass of the fuel.
$$h=\frac{E_{released\ by\ the\ combustion}}{m_{total}}\ (kJ/kg)$$

While the majority of the fuel is composed by cellulose and lignin molecules, some other chemical constituents like resins and oils may raise the particles' heat content, while particles with high mineral content may lower the particles' heat content because these minerals interfere with the combustion process. Other factors may also affect the particles' heat content.

In spite of this variability, most fire models use a constant value for heat content, typically between 18 000 kJ/kg and 20 000 kJ/kg


## Arrangement 

**Horizontally Arranged fuels**, as they have more contact with the moist soil, dry out more slowly than Vertically Arranged fuels, so they have a *higher moisture*.

**Vertically Arranged fuels** tend to let the water trickle down their length, *decreasing its moisture* absorbing capabilities. Their moisture depends more on the duration of the rainfall than on the total amount.


### [[Fuel Particle Moisture|Moisture]]
It directly affects how easily the particle can ignite and burn. High moisture content absorbs heat, delaying ignition and reducing fire intensity.