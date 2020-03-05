# Introduction

This script takes as an input a folder containing models accepted by gazebo classic / ignition gazebo,
performs a series of checks and reports issues with them (optionally tries to fix what can be automated).

# Usage
Run the script providing the root folder of your models as an argument. Optionally enable verbose output and (EXPERIMENTAL)
automatic fix of issues.

# Rules

For now it supports the following rules:
* Naming convention: Error if model name is not CamelCase
* Folder structure convention: Error if there is no model.sdf, model.config, meshes folder or if there is anything extra.
* Meshes folder content: Error if there is anything other than supported formats (dae, obj, mtl and png)
  * Texture naming: Error if not following PBR naming convention (i.e. ModelName_Diffuse.png)
* MTL diffuse: Error if not set to blender's default (0.8)
* Author name / email and model description in model.config file
* Model scale should be 1 and pose should be 0
