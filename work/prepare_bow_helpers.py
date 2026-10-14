from pathlib import Path
source=Path('outputs/Magnetgreifer/create_magnet_gripper.py').read_text()
part=source[:source.index('\ndef build():')]+source[source.index('\ndef validate():'):source.index('\ndef main():')]
part=part.replace('CubeEscape_MagnetGripper','CubeEscape_Bow_Standard').replace('MG_','BW_').replace("'magnet-gripper'","'bow'")
Path('outputs/Bogen/bow_geometry.py').write_text(part)
