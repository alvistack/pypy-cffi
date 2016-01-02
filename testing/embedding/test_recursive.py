from testing.embedding.test_basic import EmbeddingTests


class TestRecursive(EmbeddingTests):
    def test_recursive(self):
        self.prepare_module('add_recursive')
        self.compile('add_recursive-test', ['_add_recursive_cffi'])
        output = self.execute('add_recursive-test')
        assert output == ("preparing REC\n"
                          "some_callback(400)\n"
                          "adding 400 and 9\n"
                          "<<< 409 >>>\n"
                          "adding 40 and 2\n"
                          "adding 100 and -5\n"
                          "got: 42 95\n")