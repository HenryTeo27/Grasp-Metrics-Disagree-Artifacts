# DexGraspBench

A standard and unified simulation benchmark in [MuJoCo](https://github.com/google-deepmind/mujoco/) for dexterous grasping, aimed at **enabling a fair comparison across different grasp synthesis methods**, proposed in *BODex: Scalable and Efficient Robotic Dexterous Grasp Synthesis Using Bilevel Optimization [ICRA 2025]*.

[Project page](https://pku-epic.github.io/BODex/) ｜ [Paper](https://arxiv.org/abs/2412.16490) | [Grasp synthesis code](https://github.com/JYChen18/BODex)

## Introduction

### Main Usage
- Replay and test **open-loop** grasping poses/trajectories in parallel.

- Each grasping data point only needs to include:
  - Object (must be pre-processed by [MeshProcess](https://github.com/JYChen18/MeshProcess)): `obj_scale`, `obj_pose`, `obj_path`.
  - Hand: `approach_qpos` (optional), `pregrasp_qpos`, `grasp_qpos`, `squeeze_qpos`.

### Highlight

- **Comprehensive Evaluation Metrics**: Includes simulation success rate, analytic force closure metrics, penetration depth, contact quality, data diversity, and more.
- **Diverse Experimental Settings**: Covers various robotic hands (e.g., Allegro, Shadow, Leap, UR10e+Shadow), data formats (e.g., motion sequences, static poses), and scenarios (e.g., tabletop lifting, force-closure testing).
- **Multiple Baseline Methods**: Includes optimization-based grasp synthesis approaches (e.g., [DexGraspNet](https://github.com/PKU-EPIC/DexGraspNet), [FRoGGeR](https://github.com/alberthli/frogger), [SpringGrasp](https://github.com/Stanford-TML/SpringGrasp_release), [BODex](https://pku-epic.github.io/BODex/)) and data-driven baselines (e.g., CVAE, Diffusion Model, Normalizing Flow).
- **Reproducible and Standardized Testing**: The hand assets are sourced from [MuJoCo_Menagerie](https://github.com/google-deepmind/mujoco_menagerie), with modification details provided in the `assets/hand` directory. 

## Getting Started

### Installation
1. Clone the third-party library [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie).
```
git submodule update --init --recursive --progress
```
2. Install the python environment via [Anaconda](https://www.anaconda.com/). 
```
conda create -n DGBench python=3.10 
conda activate DGBench
pip install numpy==1.26.4
conda install pytorch==2.2.2 pytorch-cuda=12.1 -c pytorch -c nvidia 
pip install mujoco==3.3.2
pip install trimesh
pip install hydra-core
pip install transforms3d
pip install matplotlib
pip install scikit-learn
pip install usd-core
pip install imageio
pip install 'qpsolvers[clarabel]'
```
3. you may need to run the following command to avoid potential errors related to MKL such as `undefined symbol: iJIT_NotifyEvent`
```
conda install -c conda-forge mkl=2020.2 -y
```

### (Optional) Object Preparation
If you need the object assets used in [BODex](https://pku-epic.github.io/BODex/), please download our pre-processed object assets `DGN_2k_processed.zip` from [here](https://huggingface.co/datasets/JiayiChenPKU/BODex) and organize the unzipped folders as below. 
```
assets/object/DGN_2k
|- processed_data
|  |- core_bottle_1a7ba1f4c892e2da30711cdbdbc73924
|  |_ ...
|- scene_cfg
|  |- core_bottle_1a7ba1f4c892e2da30711cdbdbc73924
|  |_ ...
|- valid_split
|  |- all.json
|  |_ ...
```
If you need the object assets used in [Dexonomy](https://pku-epic.github.io/Dexonomy/), please download and organize `DGN_5k` and `objaverse_5k` from [here](https://huggingface.co/datasets/JiayiChenPKU/Dexonomy).

### Running

We have provided several scripts, which optionally includes format conversion, evaluation, statistic calculation, and visualization with [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) or OBJ files.

For a quick start, some example data is provided in the `output/example_shadow` directory, which can be directly evaluated by
```bash
bash script/example.sh
```

To evaluate the synthesized grasps of [BODex](https://github.com/JYChen18/BODex),
```bash
bash script/test_BODex_shadow.sh
```

To evaluate the synthesized grasps of [DexLearn](https://github.com/JYChen18/DexLearn),
```bash
bash script/test_learning_shadow.sh
```

To visualize the synthesized grasps of [Dexonomy](https://github.com/JYChen18/Dexonomy),
```bash
bash script/vis_Dexonomy.sh
```

To evaluate the conditional synthesized grasps of [DexLearn](https://github.com/JYChen18/DexLearn),
```bash
bash script/test_learning_conditional.sh
```

## Changelog
The `main` branch serves as our standard benchmark, with some adjustments to the settings compared to the [BODex](https://arxiv.org/abs/2412.16490) paper, aimed at improving the practicality. Key changes include increasing the object mass from 30g to 100g, raising the hand's kp from 1 to 5, and supporting more diverse object assets. One can further reduce friction coefficients `miu_coef` (currently 0.6 for tangential and 0.02 for torsional) to increase difficulty.

The original benchmark version is available in the `baseline` branch. This branch also includes code to test other grasp synthesis baselines, such as [DexGraspNet](https://github.com/PKU-EPIC/DexGraspNet), [FRoGGeR](https://github.com/alberthli/frogger), [SpringGrasp](https://github.com/Stanford-TML/SpringGrasp_release).


## Citation
If you find this project useful, please consider citing:
```
@article{chen2024bodex,
  title={BODex: Scalable and Efficient Robotic Dexterous Grasp Synthesis Using Bilevel Optimization},
  author={Chen, Jiayi and Ke, Yubin and Wang, He},
  journal={arXiv preprint arXiv:2412.16490},
  year={2024}
}
```
