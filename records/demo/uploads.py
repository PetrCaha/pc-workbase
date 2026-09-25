from django.core.files.uploadhandler import FileUploadHandler, StopUpload
class RejectUploads(FileUploadHandler):
    def new_file(self, *args, **kwargs):
        raise StopUpload(connection_reset=True)
    def receive_data_chunk(self, raw_data, start):
        raise StopUpload(connection_reset=True)
    def file_complete(self, file_size):
        return None
