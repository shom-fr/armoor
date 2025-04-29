Le frontend
================

.. meta::
    :description: Documentation sur le frontend

Lien vers le Projet sur le gitlab interne : `Lien <https://gitlab.shom.fr/stm1/dto/fish>`_

Build
-----
La construction du projet se fait avec la commande :

.. code-block:: bash

    ng build --configuration=production

Le resultat de la compilation sera stockée dans le dossier ``dist/``.

Deploiement automatique
------------
Un pipeline de déploiement continu est mis en place sur le git interne. Ce pipeline se déclenche lors d'un merge de la branche develop vers la branche prerelease. Les trois étapes sont :

 * Déploiement du code sur sl-noveltis-int
 * Construction angular
 * Mise a jour du fichier de configuration

Liens utiles
-----

 `Wiki-inf Shom <https://wiki-inf.shom.fr/index.php/Armoor_-_Interface_pr%C3%A9visionniste_Pr%C3%A9vOps>`_