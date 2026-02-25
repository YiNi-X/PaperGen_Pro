# 方案A: 截断模型 (No-RAG)

> 提供的上下文: 3000 字 (硬截断头部)
> 耗时: 13.25 s

---

### Introduction

The advent of autonomous driving systems has revolutionized the transportation landscape, heralding a future where vehicles can navigate safely and efficiently without human intervention. At the forefront of this technological revolution is end-to-end autonomous driving, a paradigm that aims to directly map raw sensor data to driving commands. The appeal of this approach lies in its potential to automate complex decision-making processes, thereby enhancing safety and reducing traffic congestion. Driven by the burgeoning field of deep learning, end-to-end architectures promise to transform the autonomous driving landscape by learning intricate patterns from human demonstrations, thereby imparting vehicles with the ability to perceive their environment and maneuver accordingly.

Despite the promise of end-to-end autonomous driving, several challenges have emerged that hinder the practical deployment of these systems. Traditionally, deep networks trained on human demonstrations have shown proficiency in following roads and avoiding obstacles. However, these policies lack flexibility at test time, as they are incapable of responding to real-time navigation commands or deviations from the pre-learned paths. This inflexibility limits the utility of such systems, as autonomous vehicles are often required to adapt to dynamic environments and unexpected scenarios, necessitating a degree of control and adaptability that goes beyond mere road-following.

To address this challenge, we propose an innovative solution that leverages conditional imitation learning (CIL), an approach that conditions the learning process on high-level command inputs. This method enables the autonomous vehicle, trained end-to-end, to act as a chauffeur that not only handles sensorimotor coordination but also responds to navigational commands. By conditioning the imitation learning on commands, the vehicle can be guided to take specific actions, such as turning at an upcoming intersection, enhancing its adaptability and utility in real-world scenarios.

Our research delves into the architecture of conditional imitation learning in the context of vision-based driving. We explore different architectures and evaluate their performance in realistic three-dimensional simulations of urban driving and on a 1/5 scale robotic truck, trained to drive in a residential area. Our experiments demonstrate that despite the complexity of the visual input, the vehicles can remain responsive to high-level navigational commands, showcasing the feasibility of this approach in both simulated and real-world environments.

The contributions of this paper are manifold. Firstly, we introduce a novel framework that integrates high-level commands into the end-to-end learning process, thereby creating autonomous vehicles that can be controlled and directed in a dynamic and responsive manner. Secondly, we provide a thorough evaluation of various architectures for conditional imitation learning, highlighting their strengths and challenges. Lastly, our empirical findings from both simulation and real-world trials underscore the potential of our proposed method in advancing the state-of-the-art in end-to-end autonomous driving.

In summary, this paper presents a comprehensive study on the architecture of end-to-end autonomous driving systems, with a focus on integrating high-level commands into the learning process. Our approach aims to bridge the gap between static, pre-learned policies and dynamic, real-time navigational needs, offering a promising step forward in the quest for fully autonomous vehicular systems.