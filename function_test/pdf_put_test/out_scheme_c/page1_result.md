Advances in Engineering Technology Research IBCEE 2025
ISSN:2790-1688 Volume-13-(2025)

# Design and Method Research of Intelligent Detection System for Marine Microplastics Driven by Microfluidic Chip

**Xufan Li\*, Di Yang**

School of Navigation, Wuhan University of Technology, Wuhan, China.

lixufan@whut.edu.cn

## Abstract

Marine microplastics have become a global health threat due to their widespread pollution, difficulty in degradation, and access to the human body through contaminated seafood. To deal with such a problem, this paper proposes a structural model of intelligent detection system for marine microplastics based on microfluidic chip, which is combined with microfluidic chip fluid dynamics simulation to capture seawater microplastics samples. This paper also verifies the effectiveness of microfluidic chip in sample detection and data extraction. Then the public dataset is used with Raman spectroscopy to rapidly detect seawater microplastics. Besides, efficient classification and identification of microplastics through the convolutional neural network (CNN) model are achieved. The experimental results show that the system can capture and identify a variety of microplastic particles, with 93% as the recognition and classification accuracy rate, and $98 \pm 0.02\%$ as the average ROC area. The intelligent detection system provides an innovative microplastic detection solution and efficient technical support for future marine environmental monitoring.

**Keywords:** Intelligent Detection System for Microplastics, Microfluidic Chip, Deep Learning, Fluid Dynamics Simulation.

## 1. Introduction

Microplastics refer to plastic particles with a diameter of less than 5 mm, which widely exist in ocean, freshwater, soil and atmosphere in various forms such as particles, microfibers, debris and foam plastics [1]. Microplastic pollution has become a critical issue in environmental science, especially in marine ecosystems, which has a profound impact on ecological balance, biodiversity and human health [2]. Therefore, accurately monitoring microplastic pollution in the ocean and assessing its potential impact on ecosystems and human health has been an important task for global environmental protection.

Existing microplastic detection technologies still face challenges. Traditional sampling methods, such as beach cleaning, sediment sampling and biological sampling, can provide certain information on microplastic pollution. However, it is difficult to fully cover microplastic pollution in marine environment [3]. For example, although beach cleaning is simple, it can only reflect the pollution of the shore area. It is tricky to effectively separate tiny particles. Although sediment sampling has some advantages in the detection of underwater sediments, its ability to monitor planktonic microplastics is insufficient. Biological sampling is limited to detecting the content of microplastics in organisms, making it difficult to provide comprehensive water pollution data. In addition, existing laboratory detection methods, such as microscopy, Fourier transform infrared spectroscopy (FTIR), Raman spectroscopy, etc., can generate more accurate detection results, but are often restricted by factors such as operator experience, high equipment cost and slow detection speed. It is hard to meet the monitoring needs of real-time, wide-area and high-throughput [4]. Thus, there are bottlenecks in tiny particle detection and high-precision identification [5].

In order to overcome these technical limitations, this paper proposes an intelligent detection system based on the combination of microfluidic chips and deep learning technology. The system provides a new technical path for real-time monitoring of microplastic pollution through high-precision detection combining fluid mechanics simulation, Raman spectroscopy detection and deep learning. This study uses microfluidic chip technology to achieve efficient sample separation and detection through microchannels in fluid mechanics simulation, improving the accuracy and efficiency of detection. Moreover, the combination of Raman spectroscopy and deep learning algorithm improves