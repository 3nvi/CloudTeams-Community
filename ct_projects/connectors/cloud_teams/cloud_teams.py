from ct_projects.connectors.cloud_teams.server_login import SERVER_URL, USER_PASSWD, XAPI_TEST_FOLDER
from ct_projects.connectors.cloud_teams.xmlrpc_srv import XMLRPC_Server
from ct_projects.models import Project

__author__ = 'dipap'


class CloudTeamsConnector:

    def __init__(self):
        self.srv = XMLRPC_Server(SERVER_URL, USER_PASSWD, verbose=0)
        self.PROJECTS_FOLDER_ID = XAPI_TEST_FOLDER
        self.projects = None

    def list_projects(self, q=None):
        """
        :return: A list with all projects found on BSCW
        """
        if not self.projects:
            result = []

            entries = self.srv.lst_entries(self.PROJECTS_FOLDER_ID)[1]
            for entry in entries:
                pk = entry['oid']
                title = entry['title']
                file_type_pos = entry['summary'].find('<span class="label_css">')

                # find description
                description = entry['summary'][:file_type_pos-1]

                # find publisher info
                publisher_start = entry['summary'].rfind('</span>') + len('</span>')
                publisher = entry['summary'][publisher_start + 1:]

                result.append(Project(pk=pk, title=title, description=description, publisher=publisher))

            # cache the result
            self.projects = result

        # filter out results
        if not q:
            results = self.projects
        else:
            q = q.lower()
            results = []

            for project in self.projects:
                if q in project.title.lower() or q in project.description.lower() or q in project.publisher.lower():
                    results.append(project)

        return results

    def get_project(self, pk):
        """
        :param pk: The unique identifier of the project
        :return: A project instance if found, None otherwise
        """
        for project in self.list_projects():
            if project.pk == pk:
                return project

        return None
