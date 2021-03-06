import numpy as np
import tensorflow as tf
from tentacle.board import Board
from tentacle.dnn import Pre


class DCNN1(Pre):
    def __init__(self, is_train=True, is_revive=False):
        super().__init__(is_train, is_revive)

    def diags(self, a):
        assert len(a.shape) == 2 and a.shape[0] == a.shape[1]
        valid = a.shape[0] - 5

        vecs = [a.diagonal(i) for i in range(-valid, valid + 1)]
        c = np.zeros((len(vecs), a.shape[0]))
        c[:, :] = -1
        for i, v in enumerate(vecs):
            c[i, :v.shape[0]] = v
        return c

    def regulate(self, a):
        md = self.diags(a)
        ad = self.diags(np.rot90(a))
        m = np.vstack((a, a.T, md, ad))
        return m

    def model(self, states_pl, actions_pl):
        ch1 = 32
        W_1 = self.weight_variable([1, 5, Pre.NUM_CHANNELS, ch1])
        b_1 = self.bias_variable([ch1])

        ch = 32
        W_2 = self.weight_variable([3, 3, ch1, ch])
        b_2 = self.bias_variable([ch])
        W_21 = self.weight_variable([3, 3, ch, ch])
        b_21 = self.bias_variable([ch])
#         W_22 = self.weight_variable([3, 1, ch, ch])
#         b_22 = self.bias_variable([ch])

        self.h_conv1 = tf.nn.relu(tf.nn.conv2d(states_pl, W_1, [1, 1, 1, 1], padding='VALID') + b_1)
        self.h_conv2 = tf.nn.relu(tf.nn.conv2d(self.h_conv1, W_2, [1, 1, 1, 1], padding='SAME') + b_2)
        self.h_conv21 = tf.nn.relu(tf.nn.conv2d(self.h_conv2, W_21, [1, 1, 1, 1], padding='SAME') + b_21)
#         h_conv22 = tf.nn.relu(tf.nn.conv2d(h_conv21, W_22, [1, 1, 1, 1], padding='SAME') + b_22)

        shape = self.h_conv21.get_shape().as_list()
        print(shape)
        dim = np.cumprod(shape[1:])[-1]
        h_conv_out = tf.reshape(self.h_conv21, [-1, dim])

        num_hidden = 128
        W_3 = self.weight_variable([dim, num_hidden])
        b_3 = self.bias_variable([num_hidden])
        W_4 = self.weight_variable([num_hidden, Pre.NUM_ACTIONS])
        b_4 = self.bias_variable([Pre.NUM_ACTIONS])

        self.hidden = tf.nn.softplus(tf.matmul(h_conv_out, W_3) + b_3)
        predictions = tf.matmul(self.hidden, W_4) + b_4

        self.sparse_labels = True
        cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=actions_pl, logits=predictions)
        self.loss = tf.reduce_mean(cross_entropy)
        tf.summary.scalar("loss", self.loss)
        self.optimizer = tf.train.GradientDescentOptimizer(Pre.LEARNING_RATE)
        self.opt_op = self.optimizer.minimize(self.loss)

        self.predict_probs = tf.nn.softmax(predictions)
        eq = tf.equal(tf.argmax(self.predict_probs, 1), actions_pl)
        self.eval_correct = tf.reduce_sum(tf.cast(eq, tf.int32))


    def adapt_state(self, board):
        board = board.reshape(-1, Board.BOARD_SIZE)
        board = self.regulate(board)
        return super(DCNN1, self).adapt_state(board)

    def get_input_shape(self):
        assert Board.BOARD_SIZE >= 5
        height = 6 * Board.BOARD_SIZE - 18  # row vecs + col vecs + valid(len>=5) main diag vecs + valid(len>=5) anti diag vecs
        return height, Board.BOARD_SIZE, Pre.NUM_CHANNELS

    def mid_vis(self, feed_dict):
        conv1, conv2, conv21, hide, pred = self.sess.run([self.h_conv1, self.h_conv2, self.h_conv21, self.hidden, self.predict_probs], feed_dict=feed_dict)
        np.savez(Pre.MID_VIS_FILE, feed=feed_dict[self.states_pl], conv1=conv1, conv2=conv2, conv21=conv21, hide=hide, pred=pred)


if __name__ == '__main__':
    n1 = DCNN1(is_revive=True)
    n1.run()
