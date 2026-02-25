### 2.2.2 Design and Simulation of Screen Structure

#### A Geometry

The geometry of the microfluidic device includes multiple screen layers, each of which has different screen apertures, with particles screened layer by layer according to their size during flow. The apertures of the screens are as follows. The aperture of the first screen is 0.0038 m, the aperture of the second screen is 0.0029 m, and the aperture of the third screen is 0.0015 m. These aperture designs allow particles to be filtered according to size in different screen tiers, ensuring larger particles are blocked while smaller particles are able to pass through. The left inlet of the microfluidic channel is connected to the branch outlet of the previous step, and the particle sample flows in from the left and passes through each layer of the screen for size sieving.

#### B Boundary Conditions and Physical Field Settings

(1) Inlet conditions: The fluid sample flows into the microfluidic channel through the left inlet. To maintain the laminar flow regime, delineating the inlet flow velocity ensures that the Reynolds number of the fluid is appropriate for the laminar flow mode. The initial concentration and flow rate of the particles are defined at the inlet. (2) Screen structure: The screen hierarchy is defined as a solid structure with different aperture sizes. The particles are passively filtered according to size with the change of flow rate during the flow process. (3) Pressure constraint: The pressure point constraint is used to ensure the stability of the solution of the Navier-Stokes equation. By setting the pressure in the channels, a suitable pressure gradient is ensured during the fluid flow of each screen layer to maintain flow stability.

#### C Physical Field Equation and Solution Process

In this simulation, the laminar flow model combined with the particle tracking model is used to describe the movement process of particles. The dynamic behavior of the fluid is solved by the Navier-Stokes equation, including the pressure gradient, viscous flow, and the inertial force of the particles. The trajectory of the particles is solved by the Lagrangian method. Meanwhile, whether the particles can pass through the screen aperture is judged according to the size and velocity of the particles. Navier-Stokes equation and particle tracking model are as follows:

$$\rho\left(\frac{\partial \mathbf{u}}{\partial t}+\mathbf{u} \cdot \nabla \mathbf{u}\right)=-\nabla p+\mu \nabla^{2} \mathbf{u}+\mathbf{f} \quad (1)$$

Where $\rho$ is the fluid density, $\mathbf{u}$ is the velocity vector, $p$ is the pressure, $\mu$ is the dynamic viscosity and $\mathbf{f}$ is the external force.

$$m_{p} \frac{d \mathbf{v}_{p}}{d t}=\mathbf{F}_{D}+\mathbf{F}_{g}+\mathbf{F}_{b} \quad (2)$$

Where $m_{p}$ is the particle mass, $\mathbf{v}_{p}$ is particle velocity, $\mathbf{F}_{D}$ is resistance, $\mathbf{F}_{g}$ is gravity, and $\mathbf{F}_{b}$ is buoyancy.

#### D Design Optimization and Parametric Scanning

In order to improve the screening efficiency, the configuration of screen aperture and flow rate is optimized by parametric scanning. The first layer of the screen uses a larger aperture to block large particles, and the subsequent layer of aperture decreases layer by layer to achieve fine screening. At the same time, it is required to optimize the flow rate, balance the screening efficiency and flux, and avoid too high or too low flow rate affecting the separation effect.