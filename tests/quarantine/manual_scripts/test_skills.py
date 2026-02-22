import sys

sys.path.append("C:\\Users\\Arvy Kairi\\Desktop\\bot\\kabot")

from kabot.agent.skills import SkillsLoader
from kabot.utils.helpers import get_workspace_path

loader = SkillsLoader(get_workspace_path())
skills = loader.list_skills(filter_unavailable=False)
for s in skills[:3]:
    print(s)
