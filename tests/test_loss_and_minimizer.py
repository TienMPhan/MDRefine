import unittest
import MDRefine
from MDRefine import compute_new_weights, compute_chi2, compute_D_KL, l2_regularization

class my_testcase(unittest.TestCase):
    def assertEqualObjs(self, obj1, obj2):
        
        import numpy as np
        
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            self.assertDictEqual(obj1, obj2)
        elif isinstance(obj1, np.ndarray) and isinstance(obj2, np.ndarray):
            self.assertAlmostEqual(np.sum((obj1 - obj2)**2), 0)
        elif isinstance(obj1, bool) and isinstance(obj2, bool):
            self.assertTrue(obj1 == obj2)
        elif isinstance(obj1, float) and isinstance(obj2, float):
            self.assertAlmostEqual(obj1, obj2)
        else:
            self.assertEqual(obj1, obj2)

class Test(my_testcase):
    def test_compute_new_weights_and_DKL(self):
        # import jax.numpy as np
        import numpy as np
        
        w0 = np.array([0.5, 0.5])
        correction = np.array([0., 1.])

        new_weights, logZ = compute_new_weights(w0, correction)

        self.assertAlmostEqual(np.sum(new_weights - np.array([0.73105858, 0.26894142]))**2, 0)
        self.assertAlmostEqual(logZ, -0.37988549)

        D_KL = compute_D_KL(weights_P=new_weights, correction_ff=1/2*correction, temperature=2, logZ_P=logZ)
        self.assertAlmostEqual(D_KL, 0.31265014)

    def test_l2_regularization(self):
        import numpy as np

        pars = np.array([1.2, 1.5])
        
        loss, grad = l2_regularization(pars)

        self.assertAlmostEqual(loss, 3.69)
        self.assertAlmostEqual(np.sum(grad - np.array([2.4, 3. ]))**2, 0)

    def test_compute_DeltaDeltaG_terms(self):

        import jax.numpy as jnp
        from MDRefine import load_data, compute_DeltaDeltaG_terms

        ###################################### load data #############################
        infos = {'global': {'temperature': 2.476, 'path_directory': 'tests/DATA_test'}}

        cycle_names = ['A1']

        names = {}
        for name in cycle_names:
            names[name] = []
            for string in ['AS','AD','MS','MD']:
                names[name].append((name + '_' + string))

        infos['global']['cycle_names'] = names
        infos['global']['system_names'] = [s2 for s in list(names.values()) for s2 in s]

        # force-field correction terms

        n_charges = 5

        infos['global']['names_ff_pars'] = ['DQ %i' % (i+1) for i in range(n_charges)] + ['cos eta']

        columns = []
        for i in range(n_charges):
            columns.append('DQ %i' % (i+1))
            columns.append('DQ %i%i' % (i+1,i+1))
        for i in range(n_charges):
            for j in range(i+1,n_charges):
                columns.append('DQ %i%i' % (i+1,j+1))
        columns.append('cos eta')

        # only methylated (M) systems have a force-field correction

        for name in infos['global']['system_names']: infos[name] = {}

        for name in infos['global']['cycle_names'].keys():
            for s in ['D', 'S']:
                infos[name + '_M' + s]['ff_terms'] = columns

        names_charges = ['N6', 'H61', 'N1', 'C10', 'H101/2/3']

        def ff_correction(phi, ff_terms):

            n_charges = 5

            phi_vector = []
            for i in range(n_charges):
                phi_vector.extend([phi[i], phi[i]**2])
            for i in range(n_charges):
                for j in range(i+1,n_charges):
                    phi_vector.append(phi[i]*phi[j])
            phi_vector.append(-phi[-1])
            phi_vector = jnp.array(phi_vector)

            correction = jnp.matmul(ff_terms, phi_vector)

            return correction

        for k in infos['global']['system_names']:
            if k[-2] == 'M': 
                infos[k]['ff_correction'] = ff_correction

        data = load_data(infos)

        ############ test #########################################################
        
        out = compute_DeltaDeltaG_terms(data, logZ_P={'A1_MS': 1., 'A1_MD': 1.5})
        out_test = ({'A1_MS': 255.7655459570046, 'A1_MD': 256.2379948027602}, {'A1': 135.84140982133923}, 67.92070491066961)

        for i in [0, 1]:
            self.assertEqual(out_test[i].keys(), out[i].keys())

            for k in out_test[i].keys():
                self.assertAlmostEqual(out_test[i][k], out[i][k])

        self.assertAlmostEqual(out_test[2], out[2])

    def test_compute_chi2(self):

        import jax.numpy as jnp
        import numpy as np
        from MDRefine import load_data, compute_chi2

        infos = {'global': {
            'path_directory': 'tests/DATA_test',
            'system_names': ['AAAA', 'CAAU'],
            'g_exp': ['backbone1_gamma_3J', 'backbone2_beta_epsilon_3J', 'sugar_3J', 'NOEs' , ('uNOEs', '<')],
            'forward_qs': ['backbone1_gamma', 'backbone2_beta_epsilon','sugar'],
            'obs': ['NOEs', 'uNOEs'],
            'forward_coeffs': 'original_fm_coeffs'}}

        def forward_model_fun(fm_coeffs, forward_qs, selected_obs=None):

            # 1. compute the cosine (which is the quantity you need in the forward model;
            # you could do this just once before loading data)
            forward_qs_cos = {}

            for type_name in forward_qs.keys():
                forward_qs_cos[type_name] = jnp.cos(forward_qs[type_name])

            # if you have selected_obs, compute only the corresponding observables
            if selected_obs is not None:
                for type_name in forward_qs.keys():
                    forward_qs_cos[type_name] = forward_qs_cos[type_name][:,selected_obs[type_name+'_3J']]

            # 2. compute observables (forward_qs_out) through forward model
            forward_qs_out = {
                'backbone1_gamma_3J': fm_coeffs[0]*forward_qs_cos['backbone1_gamma']**2 + fm_coeffs[1]*forward_qs_cos['backbone1_gamma'] + fm_coeffs[2],
                'backbone2_beta_epsilon_3J': fm_coeffs[3]*forward_qs_cos['backbone2_beta_epsilon']**2 + fm_coeffs[4]*forward_qs_cos['backbone2_beta_epsilon'] + fm_coeffs[5],
                'sugar_3J': fm_coeffs[6]*forward_qs_cos['sugar']**2 + fm_coeffs[7]*forward_qs_cos['sugar'] + fm_coeffs[8] }

            return forward_qs_out

        infos['global']['forward_model'] = forward_model_fun
        infos['global']['names_ff_pars'] = ['sin alpha', 'cos alpha']

        def ff_correction(pars, f):
            out = jnp.matmul(pars, (f[:, [0, 6]] + f[:, [1, 7]] + f[:, [2, 8]]).T)
            return out

        infos['global']['ff_correction'] = ff_correction

        data = load_data(infos)

        out = compute_chi2(data.mol['AAAA'].ref, data.mol['AAAA'].weights, data.mol['AAAA'].g, data.mol['AAAA'].gexp)

        out_test = ({'backbone1_gamma_3J': np.array([2.2820567 , 2.37008063]),
            'backbone2_beta_epsilon_3J': np.array([6.39268088, 3.86126331]),
            'sugar_3J': np.array([3.71089481, 4.77456358]),
            'NOEs': np.array([1.87342536e-03, 4.30196379e-05]),
            'uNOEs': np.array([1.33028693e-05, 5.82998086e-06])},
            {'backbone1_gamma_3J': np.array(1.08493846),
            'backbone2_beta_epsilon_3J': np.array(1.88280674),
            'sugar_3J': np.array(2.14070494),
            'NOEs': np.array(6.1036602),
            'uNOEs': np.array(0.)},
            {'backbone1_gamma_3J': np.array([-1.0119622 ,  0.24672042]),
            'backbone2_beta_epsilon_3J': np.array([-1.37154608,  0.0408422 ]),
            'sugar_3J': np.array([1.14059654, 0.91637572]),
            'NOEs': np.array([ 2.40941428, -0.54624448]),
            'uNOEs': np.array([0., 0.])},
            np.array(11.21211034))

        for i in range(3):
            self.assertSetEqual(set(out_test[i].keys()), set(out[i].keys()))
            for k in out_test[0].keys():
                self.assertAlmostEqual(np.sum((out_test[i][k] - out[i][k])**2), 0)
        
        self.assertAlmostEqual(out_test[3], out[3])

        # if_separate = True (no change)
        out = compute_chi2(data.mol['AAAA'].ref, data.mol['AAAA'].weights, data.mol['AAAA'].g, data.mol['AAAA'].gexp, True)
        
        for i in range(3):
            self.assertSetEqual(set(out_test[i].keys()), set(out[i].keys()))
            for k in out_test[0].keys():
                self.assertAlmostEqual(np.sum((out_test[i][k] - out[i][k])**2), 0)
        
        self.assertAlmostEqual(out_test[3], out[3])

    def test_gamma_function(self):
        
        import jax.numpy as jnp
        import numpy as np
        from MDRefine import load_data, gamma_function

        infos = {'global': {
            'path_directory': 'tests/DATA_test',
            'system_names': ['AAAA'],
            'g_exp': ['backbone1_gamma_3J', 'backbone2_beta_epsilon_3J', 'sugar_3J', 'NOEs' , ('uNOEs', '<')],
            'forward_qs': ['backbone1_gamma', 'backbone2_beta_epsilon','sugar'],
            'obs': ['NOEs', 'uNOEs'],
            'forward_coeffs': 'original_fm_coeffs'}}

        def forward_model_fun(fm_coeffs, forward_qs, selected_obs=None):

            # 1. compute the cosine (which is the quantity you need in the forward model;
            # you could do this just once before loading data)
            forward_qs_cos = {}

            for type_name in forward_qs.keys():
                forward_qs_cos[type_name] = jnp.cos(forward_qs[type_name])

            # if you have selected_obs, compute only the corresponding observables
            if selected_obs is not None:
                for type_name in forward_qs.keys():
                    forward_qs_cos[type_name] = forward_qs_cos[type_name][:,selected_obs[type_name+'_3J']]

            # 2. compute observables (forward_qs_out) through forward model
            forward_qs_out = {
                'backbone1_gamma_3J': fm_coeffs[0]*forward_qs_cos['backbone1_gamma']**2 + fm_coeffs[1]*forward_qs_cos['backbone1_gamma'] + fm_coeffs[2],
                'backbone2_beta_epsilon_3J': fm_coeffs[3]*forward_qs_cos['backbone2_beta_epsilon']**2 + fm_coeffs[4]*forward_qs_cos['backbone2_beta_epsilon'] + fm_coeffs[5],
                'sugar_3J': fm_coeffs[6]*forward_qs_cos['sugar']**2 + fm_coeffs[7]*forward_qs_cos['sugar'] + fm_coeffs[8] }

            return forward_qs_out

        infos['global']['forward_model'] = forward_model_fun
        infos['global']['names_ff_pars'] = ['sin alpha', 'cos alpha']

        def ff_correction(pars, f):
            out = jnp.matmul(pars, (f[:, [0, 6]] + f[:, [1, 7]] + f[:, [2, 8]]).T)
            return out

        infos['global']['ff_correction'] = ff_correction

        data = load_data(infos)

        flatten_g = np.hstack([data.mol['AAAA'].g[k] for k in data.mol['AAAA'].n_experiments.keys()])
        flatten_gexp = np.vstack([data.mol['AAAA'].gexp[k] for k in data.mol['AAAA'].n_experiments.keys()])

        alpha = 1.5

        # fixed random values
        lambdas = np.array([0.02276649, 0.92055914, 0.54435632, 0.28184011, 0.75414035,
            0.75551687, 0.47772936, 0.8749338 , 0.7059772 , 0.96640172])

        out = gamma_function(lambdas, flatten_g, flatten_gexp, data.mol['AAAA'].weights, alpha, True)

        out_test = ((6.27231308),
            np.array([ 3.34791024e-01,  3.63254555e+00,  6.39012045e+00,  1.29484769e+00,
                    4.05246153e+00,  1.92475534e+00, -8.35131574e-06,  5.11595544e-05,
                    1.48046374e-04,  7.04939569e-05]),
            np.array([3.54204586e+00, 1.47434153e+00, 3.89708214e+00,
                        3.45636268e+00, 4.92762134e-01, 4.02511408e+00,
                        7.82813097e-04, 3.06092488e-05, 1.01479652e-05,
                        1.75379015e-06]))

        self.assertAlmostEqual(out[0], out_test[0])
        self.assertAlmostEqual(np.sum((out[1] - out_test[1])**2), 0)
        self.assertAlmostEqual(np.sum((out[2] - out_test[2])**2), 0)

    # def test_loss_function(self):
    
    def test_minimizer(self):
    
        import pickle
        import jax.numpy as jnp
        import numpy as np
        from MDRefine import load_data, minimizer

        infos = {'global': {
            'path_directory': 'tests/DATA_test',
            'system_names': ['AAAA', 'CAAU'],
            'g_exp': ['backbone1_gamma_3J', 'backbone2_beta_epsilon_3J', 'sugar_3J', 'NOEs'],# , ('uNOEs', '<')],
            'forward_qs': ['backbone1_gamma', 'backbone2_beta_epsilon','sugar'],
            'obs': ['NOEs'],#, 'uNOEs'],
            'forward_coeffs': 'original_fm_coeffs'}}

        def forward_model_fun(fm_coeffs, forward_qs, selected_obs=None):

            # 1. compute the cosine (which is the quantity you need in the forward model;
            # you could do this just once before loading data)
            forward_qs_cos = {}

            for type_name in forward_qs.keys():
                forward_qs_cos[type_name] = jnp.cos(forward_qs[type_name])

            # if you have selected_obs, compute only the corresponding observables
            if selected_obs is not None:
                for type_name in forward_qs.keys():
                    forward_qs_cos[type_name] = forward_qs_cos[type_name][:,selected_obs[type_name+'_3J']]

            # 2. compute observables (forward_qs_out) through forward model
            forward_qs_out = {
                'backbone1_gamma_3J': fm_coeffs[0]*forward_qs_cos['backbone1_gamma']**2 + fm_coeffs[1]*forward_qs_cos['backbone1_gamma'] + fm_coeffs[2],
                'backbone2_beta_epsilon_3J': fm_coeffs[3]*forward_qs_cos['backbone2_beta_epsilon']**2 + fm_coeffs[4]*forward_qs_cos['backbone2_beta_epsilon'] + fm_coeffs[5],
                'sugar_3J': fm_coeffs[6]*forward_qs_cos['sugar']**2 + fm_coeffs[7]*forward_qs_cos['sugar'] + fm_coeffs[8] }

            return forward_qs_out

        infos['global']['forward_model'] = forward_model_fun
        infos['global']['names_ff_pars'] = ['sin alpha', 'cos alpha']

        def ff_correction(pars, f):
            out = jnp.matmul(pars, (f[:, [0, 6]] + f[:, [1, 7]] + f[:, [2, 8]]).T)
            return out

        infos['global']['ff_correction'] = ff_correction

        data = load_data(infos)

        result = minimizer(data, alpha=1.5)

        test_result = pickle.load(open('tests/DATA_test/result1.pkl', 'rb'))

        self.assertAlmostEqual(result.loss, test_result['loss']) # float

        for k in result.min_lambdas.keys():
            self.assertAlmostEqual(result.abs_difference[k] - test_result['abs_difference'][k], 0)

            for k2 in result.min_lambdas[k].keys():
                self.assertAlmostEqual(np.sum((result.min_lambdas[k][k2] - test_result['min_lambdas'][k][k2])**2), 0) # array
                self.assertAlmostEqual(np.sum((result.av_g[k][k2] - test_result['av_g'][k][k2])**2), 0) # array

            self.assertAlmostEqual(result.minis[k].fun, test_result['minis'][k].fun) # float
            self.assertAlmostEqual(np.sum((result.minis[k].jac - test_result['minis'][k].jac)**2), 0) # array
            self.assertTrue(result.minis[k].success == test_result['minis'][k].success) # boolean
            self.assertAlmostEqual(np.sum((result.minis[k].x - test_result['minis'][k].x)**2), 0) # array
            self.assertAlmostEqual(np.sum((result.weights_new[k] - test_result['weights_new'][k])**2), 0) # array

        self.assertDictEqual(result.D_KL_alpha, test_result['D_KL_alpha']) # dict
        
        # self.assertDictEqual(result.chi2, test_result['chi2']) # dict
        self.assertEqualObjs(result.chi2, test_result['chi2'])

        # self.assertDictEqual(result.logZ_new, test_result['logZ_new']) # dict
        self.assertEqualObjs(result.logZ_new, test_result['logZ_new'])



if __name__ == "__main__":
    unittest.main()